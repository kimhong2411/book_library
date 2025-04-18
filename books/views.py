import os
import re
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from .models import Book
from .forms import BookForm,ThreadForm
from gtts import gTTS
import requests  # AI API 호출을 위한 requests 모듈
import openai
from django.contrib.auth.decorators import login_required
from .models import Thread  # 아직 없지만 게시글도 보여줄 예정!
from django.http import HttpResponseForbidden





def index(request):
    books = Book.objects.all()
    return render(request, 'books/index.html', {'books': books})

def detail(request, pk):
    book = get_object_or_404(Book, pk=pk)
    threads = Thread.objects.filter(book=book).order_by('-id')  # 도서에 달린 게시글들
    context = {
        'book': book,
        'threads': threads,
    }
    return render(request, 'books/detail.html', context)



def sanitize_filename(filename):
    """
    Windows에서 허용되지 않는 문자: \ / : * ? " < > |
    그 외에도 상황에 따라 제거할 문자나 규칙을 추가할 수 있습니다.
    """
    # 1) 불가능한 문자 제거
    filename = re.sub(r'[\\/*?:"<>|]', '', filename)
    # 2) 공백 -> 언더스코어
    filename = filename.replace(' ', '_')
    return filename

@login_required
def create(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)

            # AI로 작가 정보를 가져오기
            author_data = get_ai_author_data(book.author)
            if author_data:
                book.author_info = author_data.get('author_info', '')
                book.author_works = author_data.get('author_works', '')

            # gTTS 텍스트
            tts_text = f"{book.title}. {book.description}. 저자: {book.author}"
            
            # 폴더 생성 (media/tts) 코드
            tts_dir = os.path.join(settings.MEDIA_ROOT, 'tts')
            if not os.path.exists(tts_dir):
                os.makedirs(tts_dir)
            
            # 파일명 정규화
            safe_title = sanitize_filename(book.title)
            tts_filename = f"{safe_title}.mp3"
            tts_path = os.path.join(tts_dir, tts_filename)

            # gTTS 음성 파일 생성
            tts = gTTS(text=tts_text, lang='ko')
            tts.save(tts_path)

            # Book 모델에 audio_file 경로 저장
            book.audio_file = os.path.join('tts', tts_filename)
            book.save()

            return redirect('books:detail', pk=book.pk)
    else:
        form = BookForm()
    return render(request, 'books/create.html', {'form': form})


def update(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            return redirect('books:detail', pk=book.pk)
    else:
        form = BookForm(instance=book)
    return render(request, 'books/update.html', {'form': form, 'book': book})


def delete(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        book.delete()
        return redirect('books:index')
    return render(request, 'books/delete.html', {'book': book})

# --- AI API 연동 함수 수정 --- 
def get_ai_author_data(author_name):
    """
    AI API (예: GPT 또는 OpenAI API)를 호출해 작가 정보와 대표작 목록을 가져옵니다.
    """
    openai.api_key = settings.OPENAI_API_KEY  # settings.py에서 API 키 가져오기
    
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",  # 사용할 GPT 모델 (필요에 따라 다를 수 있음)
            prompt=f"{author_name}의 작가 정보와 대표작 목록을 알려줘.",
            max_tokens=150
        )
        
        # API 응답 처리
        if response and 'choices' in response:
            text = response['choices'][0]['text']
            
            # 작가 정보와 대표작 목록을 분리하는 간단한 방법 예시
            # 이 부분은 AI 응답의 형식에 따라 다르게 처리될 수 있음
            author_info = ""
            author_works = ""
            
            # 예시: AI가 정보와 대표작 목록을 줄바꿈으로 구분했다고 가정
            lines = text.strip().split('\n')
            if len(lines) > 0:
                author_info = lines[0]  # 첫 번째 줄을 작가 정보로
            if len(lines) > 1:
                author_works = lines[1]  # 두 번째 줄을 대표작 목록으로
            
            return {'author_info': author_info, 'author_works': author_works}
        
    except Exception as e:
        print(f"OpenAI API 호출 에러: {e}")
    
    return None

def thread_create(request, book_pk):
    book = get_object_or_404(Book, pk=book_pk)

    if request.method == 'POST':
        form = ThreadForm(request.POST, request.FILES)
        if form.is_valid():
            thread = form.save(commit=False)
            thread.book = book  # 직접 연결
            thread.save()
            return redirect('books:detail', book.pk)
    else:
        form = ThreadForm()

    context = {'form': form, 'book': book}
    return render(request, 'books/thread_create.html', context)

def thread_detail(request, book_pk, thread_pk):
    book = get_object_or_404(Book, pk=book_pk)
    thread = get_object_or_404(Thread, pk=thread_pk, book=book)

    context = {
        'book': book,
        'thread': thread,
    }
    return render(request, 'books/thread_detail.html', context)

def thread_update(request, book_pk, thread_pk):
    book = get_object_or_404(Book, pk=book_pk)
    thread = get_object_or_404(Thread, pk=thread_pk, book=book)

    if request.method == 'POST':
        form = ThreadForm(request.POST, request.FILES, instance=thread)
        if form.is_valid():
            form.save()
            return redirect('books:thread_detail', book.pk, thread.pk)
    else:
        form = ThreadForm(instance=thread)

    context = {'form': form, 'book': book, 'thread': thread}
    return render(request, 'books/thread_update.html', context)

def thread_delete(request, book_pk, thread_pk):
    book = get_object_or_404(Book, pk=book_pk)
    thread = get_object_or_404(Thread, pk=thread_pk, book=book)
    #
    #  🔒 작성자만 삭제 가능하도록 체크
    if request.user != thread.user:
        return HttpResponseForbidden("당신은 이 글을 삭제할 권한이 없습니다.")

    if request.method == 'POST':
        thread.delete()
        return redirect('books:detail', book.pk)

    context = {'book': book, 'thread': thread}
    return render(request, 'books/thread_delete.html', context)

@login_required
def like(request, book_pk, thread_pk):
    thread = get_object_or_404(Thread, pk=thread_pk)

    if request.user in thread.likes.all():
        thread.likes.remove(request.user)
    else:
        thread.likes.add(request.user)

    return redirect('books:thread_detail', book_pk, thread_pk)
