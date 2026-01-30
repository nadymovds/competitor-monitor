# -*- coding: utf-8 -*-

# Отключаем предупреждения о небезопасных SSL соединениях
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Импорты
import os
import hashlib
import json
import re
import requests
import aiohttp
import asyncio
import random
import time
from datetime import datetime, timedelta
from supabase import create_client, Client
from bs4 import BeautifulSoup

# Импорты для Playwright
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Импорты для PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

print("✅ Зависимости импортированы")

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_GROUP_CHAT_ID = os.environ.get("TELEGRAM_GROUP_CHAT_ID")
NEWS_PERIOD_DAYS = int(os.environ.get("NEWS_PERIOD_DAYS", "7"))

# === LLM ===
NEWS_LLM_MODEL = "llama-3.3-70b-versatile"
LLM_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# === ТАЙМАУТЫ И ЛИМИТЫ ===
NEWS_REQUEST_TIMEOUT = 30
NEWS_PLAYWRIGHT_TIMEOUT = 30000
MAX_POSTS_PER_CHANNEL = 50
DELAY_BETWEEN_CHANNELS = 3
MAX_POSTS_IN_DIGEST = 100
MAX_CONCURRENT_LLM_NEWS = 3
DEFAULT_DIGEST_PERIOD_DAYS = 7

# === РОТАЦИЯ USER-AGENT ===
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

# === ИНИЦИАЛИЗАЦИЯ SUPABASE ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === СЕМАФОРЫ ===
browser_semaphore = None
llm_semaphore = None

def init_semaphores():
    global browser_semaphore, llm_semaphore
    browser_semaphore = asyncio.Semaphore(1)
    llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_NEWS)

# === РЕГИСТРАЦИЯ ШРИФТОВ ===
def register_fonts():
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]
    try:
        if os.path.exists(font_paths[0]):
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_paths[0]))
            if os.path.exists(font_paths[1]):
                pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_paths[1]))
            return 'DejaVuSans'
    except:
        pass
    return 'Helvetica'

FONT_NAME = register_fonts()

# === ИКОНКИ КАТЕГОРИЙ ДЛЯ PDF ===
CATEGORY_ICONS = {
    'Технологии': '⚙',
    'Законодательство': '§',
    'Происшествия': '⚠',
    'Развлекательный контент': '★',
    'Погодные условия': '☁',
    'Прочее': '•',
}
DEFAULT_CATEGORY_ICON = '▸'

print("✅ Конфигурация загружена")

# ============================================================================
# TELEGRAM
# ============================================================================

def send_telegram_message(message: str) -> bool:
    success = False
    chat_ids = [TELEGRAM_CHAT_ID, TELEGRAM_GROUP_CHAT_ID]
    for chat_id in chat_ids:
        if chat_id:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=30)
                success = True
            except:
                pass
    return success

def send_telegram_document(file_path: str, caption: str = "") -> bool:
    success = False
    chat_ids = [TELEGRAM_CHAT_ID, TELEGRAM_GROUP_CHAT_ID]
    for chat_id in chat_ids:
        if chat_id:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
                with open(file_path, 'rb') as f:
                    requests.post(url, data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'},
                                 files={'document': f}, timeout=60)
                success = True
            except:
                pass
    return success

# ============================================================================
# УТИЛИТЫ
# ============================================================================

def calculate_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def clean_post_text(html_text: str) -> str:
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, 'lxml')
    text = soup.get_text(separator='\n', strip=True)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def parse_views_count(views_str: str) -> int:
    if not views_str:
        return 0
    views_str = views_str.strip().upper()
    try:
        if 'M' in views_str:
            return int(float(views_str.replace('M', '')) * 1_000_000)
        elif 'K' in views_str:
            return int(float(views_str.replace('K', '')) * 1_000)
        else:
            return int(re.sub(r'[^\d]', '', views_str))
    except (ValueError, TypeError):
        return 0

def extract_title(text: str) -> str:
    if not text:
        return ""
    first_line = text.strip().split('\n')[0].strip()
    if len(first_line) > 100:
        first_line = first_line[:97] + "..."
    return first_line

# ============================================================================
# ПАРСИНГ КАНАЛОВ (t.me/s/)
# ============================================================================

async def fetch_channel_page(channel_username: str, browser_context, before_id: int = None) -> str:
    """Загружает HTML страницы публичного Telegram-канала через Playwright."""
    url = f"https://t.me/s/{channel_username}"
    if before_id:
        url += f"?before={before_id}"

    async with browser_semaphore:
        page = await browser_context.new_page()
        try:
            # Stealth-режим
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
                window.chrome = { runtime: {} };
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            # Блокировка тяжёлых медиа и аналитики
            await page.route("**/*.{mp4,webm,mp3,wav,avi,mov,flv}", lambda route: route.abort())
            await page.route("**/*google-analytics*", lambda route: route.abort())
            await page.route("**/*googletagmanager*", lambda route: route.abort())
            await page.route("**/*mc.yandex*", lambda route: route.abort())

            await page.goto(url, wait_until='domcontentloaded', timeout=NEWS_PLAYWRIGHT_TIMEOUT)

            try:
                await page.wait_for_selector('div.tgme_widget_message_wrap', timeout=15000)
            except PlaywrightTimeout:
                print(f"  ⚠️ Селектор сообщений не найден для @{channel_username}")
                return ""

            html = await page.content()
            return html
        except Exception as e:
            print(f"  ❌ Ошибка загрузки @{channel_username}: {e}")
            return ""
        finally:
            await page.close()


def parse_posts_from_html(html: str, channel_username: str) -> list:
    """Парсит посты из HTML страницы t.me/s/."""
    if not html:
        return []

    soup = BeautifulSoup(html, 'lxml')
    message_wraps = soup.find_all('div', class_='tgme_widget_message_wrap')
    posts = []

    for wrap in message_wraps:
        try:
            message_div = wrap.find('div', class_='tgme_widget_message')
            if not message_div:
                continue

            # message_id из data-post="channel/123"
            data_post = message_div.get('data-post', '')
            if '/' not in data_post:
                continue
            message_id = int(data_post.split('/')[-1])

            # Текст поста
            text_div = message_div.find('div', class_='tgme_widget_message_text')
            raw_html = str(text_div) if text_div else ""
            text = clean_post_text(raw_html)

            # Дата публикации
            time_tag = message_div.find('time')
            post_date = None
            if time_tag and time_tag.get('datetime'):
                post_date = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))

            # Просмотры
            views_span = message_div.find('span', class_='tgme_widget_message_views')
            views = parse_views_count(views_span.get_text() if views_span else "")

            # Медиа
            has_photo = bool(message_div.find('a', class_='tgme_widget_message_photo_wrap'))
            has_video = bool(message_div.find('video') or message_div.find(class_='tgme_widget_message_video'))
            has_document = bool(message_div.find('div', class_='tgme_widget_message_document'))

            post_url = f"https://t.me/{channel_username}/{message_id}"

            posts.append({
                'message_id': message_id,
                'post_url': post_url,
                'text': text,
                'post_date': post_date,
                'has_photo': has_photo,
                'has_video': has_video,
                'has_document': has_document,
                'views': views,
                'content_hash': calculate_hash(text) if text else None,
            })
        except Exception as e:
            print(f"  ⚠️ Ошибка парсинга поста: {e}")
            continue

    posts.sort(key=lambda p: p['message_id'])
    return posts


async def fetch_channel_posts(channel_username: str, browser_context,
                              after_message_id: int = None, max_posts: int = MAX_POSTS_PER_CHANNEL) -> list:
    """Загружает новые посты канала с пагинацией через ?before=."""
    all_posts = []
    before_id = None

    while len(all_posts) < max_posts:
        html = await fetch_channel_page(channel_username, browser_context, before_id=before_id)
        if not html:
            break

        page_posts = parse_posts_from_html(html, channel_username)
        if not page_posts:
            break

        # Фильтруем только новые посты (message_id > after_message_id)
        if after_message_id:
            page_posts = [p for p in page_posts if p['message_id'] > after_message_id]

        if not page_posts:
            break

        all_posts.extend(page_posts)

        # Если на странице меньше ~20 постов — это последняя страница
        if len(parse_posts_from_html(html, channel_username)) < 10:
            break

        # Пагинация: загрузить старее самого раннего поста на странице
        oldest_id = min(p['message_id'] for p in page_posts)

        # Если уже дошли до after_message_id — хватит
        if after_message_id and oldest_id <= after_message_id:
            break

        before_id = oldest_id
        await asyncio.sleep(1)

    # Обрезаем до лимита и сортируем
    all_posts.sort(key=lambda p: p['message_id'])
    return all_posts[:max_posts]

# ============================================================================
# ОПЕРАЦИИ С SUPABASE
# ============================================================================

def get_active_channels() -> list:
    """Выборка активных каналов из news_channels."""
    try:
        result = supabase.table('news_channels').select('*').eq('is_active', True).execute()
        return result.data or []
    except Exception as e:
        print(f"❌ Ошибка получения каналов: {e}")
        return []

def get_categories() -> list:
    """Выборка категорий из news_categories с сортировкой по sort_order."""
    try:
        result = supabase.table('news_categories').select('*').order('sort_order').execute()
        return result.data or []
    except Exception as e:
        print(f"❌ Ошибка получения категорий: {e}")
        return []

def save_post(channel_id: int, post_data: dict) -> int | None:
    """Upsert поста в news_posts. Возвращает id записи."""
    try:
        data = {
            'channel_id': channel_id,
            'message_id': post_data['message_id'],
            'post_url': post_data['post_url'],
            'content_text': post_data.get('text', ''),
            'post_date': post_data['post_date'].isoformat() if post_data.get('post_date') else None,
            'has_photo': post_data.get('has_photo', False),
            'has_video': post_data.get('has_video', False),
            'has_document': post_data.get('has_document', False),
            'views_count': post_data.get('views', 0),
            'content_hash': post_data.get('content_hash'),
        }
        result = supabase.table('news_posts').upsert(data, on_conflict='channel_id,message_id').execute()
        if result.data:
            return result.data[0].get('id')
        return None
    except Exception as e:
        print(f"  ⚠️ Ошибка сохранения поста {post_data.get('message_id')}: {e}")
        return None

def save_post_categories(post_id: int, categories_list: list) -> None:
    """Вставка категорий поста в news_post_categories (пропуск при конфликте, не перезаписывать ручные)."""
    for cat in categories_list:
        try:
            data = {
                'post_id': post_id,
                'category_id': cat['category_id'],
                'confidence': cat.get('confidence', 0.0),
                'is_manual': False,
            }
            supabase.table('news_post_categories').upsert(
                data, on_conflict='post_id,category_id', ignore_duplicates=True
            ).execute()
        except Exception as e:
            print(f"  ⚠️ Ошибка сохранения категории {cat.get('category_id')} для поста {post_id}: {e}")

def update_channel_after_scan(channel_id: int, last_message_id: int) -> None:
    """Обновление last_message_id и last_scan_at после сканирования канала."""
    try:
        supabase.table('news_channels').update({
            'last_message_id': last_message_id,
            'last_scan_at': datetime.now().isoformat(),
        }).eq('id', channel_id).execute()
    except Exception as e:
        print(f"  ⚠️ Ошибка обновления канала {channel_id}: {e}")

def mark_post_processed(post_id: int, title: str, summary: str) -> None:
    """Пометка поста как обработанного LLM с заголовком и summary."""
    try:
        supabase.table('news_posts').update({
            'is_processed': True,
            'title': title,
            'summary': summary,
        }).eq('id', post_id).execute()
    except Exception as e:
        print(f"  ⚠️ Ошибка обновления поста {post_id}: {e}")

def get_unprocessed_posts(period_start: datetime) -> list:
    """Выборка необработанных постов начиная с period_start."""
    try:
        result = (supabase.table('news_posts')
                  .select('*, news_channels(username, title)')
                  .eq('is_processed', False)
                  .gte('post_date', period_start.isoformat())
                  .order('post_date', desc=False)
                  .execute())
        return result.data or []
    except Exception as e:
        print(f"❌ Ошибка получения необработанных постов: {e}")
        return []

def get_posts_for_digest(period_start: datetime, period_end: datetime) -> list:
    """Выборка обработанных постов с видимыми категориями для дайджеста."""
    try:
        result = (supabase.table('news_posts')
                  .select('*, news_channels(username, title), news_post_categories(category_id, confidence, news_categories(id, name, color, sort_order, is_visible))')
                  .eq('is_processed', True)
                  .gte('post_date', period_start.isoformat())
                  .lte('post_date', period_end.isoformat())
                  .order('post_date', desc=True)
                  .limit(MAX_POSTS_IN_DIGEST)
                  .execute())
        return result.data or []
    except Exception as e:
        print(f"❌ Ошибка получения постов для дайджеста: {e}")
        return []

def save_digest(digest_data: dict, post_ids: list) -> int | None:
    """Сохранение дайджеста и связей с постами. Возвращает id дайджеста."""
    try:
        result = supabase.table('news_digests').insert(digest_data).execute()
        if not result.data:
            return None
        digest_id = result.data[0]['id']

        for rank, post_id in enumerate(post_ids, start=1):
            supabase.table('news_digest_posts').insert({
                'digest_id': digest_id,
                'post_id': post_id,
                'rank_in_category': rank,
            }).execute()

        return digest_id
    except Exception as e:
        print(f"❌ Ошибка сохранения дайджеста: {e}")
        return None

# ============================================================================
# LLM-АНАЛИЗ
# ============================================================================

async def call_llm_async(prompt: str, session: aiohttp.ClientSession, max_tokens: int = 500) -> str | None:
    """Вызов OpenRouter API с семафором и retry."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": NEWS_LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    for attempt in range(2):
        try:
            async with llm_semaphore:
                async with session.post(LLM_API_URL, headers=headers, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=90)) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            if attempt < 1:
                print(f"  ⚠️ LLM retry после ошибки: {e}")
                await asyncio.sleep(3)
            else:
                print(f"  ❌ LLM ошибка после 2 попыток: {e}")
                return None
    return None


async def categorize_post(post_text: str, categories: list, session: aiohttp.ClientSession) -> list:
    """Определение категорий поста через LLM. Возвращает список {category_id, confidence}."""
    categories_desc = "\n".join(
        f"- ID {cat['id']}: {cat['name']}" + (f" — {cat['description']}" if cat.get('description') else "")
        for cat in categories
    )

    prompt = f"""Определи категории для следующего поста из Telegram-канала о транспорте и логистике.

ТЕКСТ ПОСТА:
{post_text[:2000]}

ДОСТУПНЫЕ КАТЕГОРИИ:
{categories_desc}

ПРАВИЛА:
- Выбери от 1 до 3 наиболее подходящих категорий
- Для каждой категории укажи уверенность от 0.0 до 1.0
- Если пост не относится ни к одной категории — верни пустой список
- Отвечай ТОЛЬКО JSON, без пояснений

ФОРМАТ ОТВЕТА:
{{"categories": [{{"category_id": N, "confidence": 0.85}}]}}"""

    response = await call_llm_async(prompt, session, max_tokens=300)
    if not response:
        return []

    try:
        # Извлечение JSON из ответа
        json_str = response.strip()
        json_str = re.sub(r'^```json?\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)

        json_match = re.search(r'\{[^{}]*"categories"[^}]*\[.*?\]\s*\}', json_str, re.DOTALL)
        if json_match:
            json_str = json_match.group()

        result = json.loads(json_str)
        raw_categories = result.get('categories', [])

        # Валидация: проверяем что category_id существует в списке категорий
        valid_ids = {cat['id'] for cat in categories}
        validated = []
        for cat in raw_categories:
            cat_id = cat.get('category_id')
            confidence = cat.get('confidence', 0.0)
            if cat_id in valid_ids and 0.0 <= confidence <= 1.0:
                validated.append({'category_id': cat_id, 'confidence': round(confidence, 2)})

        return validated[:3]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  ⚠️ Ошибка парсинга категорий LLM: {e}")
        return []


async def generate_summary(post_text: str, session: aiohttp.ClientSession) -> str:
    """Генерация краткого содержания поста (1-2 предложения, до 300 символов)."""
    prompt = f"""Напиши краткое содержание следующего поста из Telegram-канала о транспортно-логистической отрасли.

ТЕКСТ ПОСТА:
{post_text[:2000]}

ПРАВИЛА:
- 1-2 предложения, максимум 300 символов
- Только на русском языке
- Фокус на ключевых фактах: что произошло, кто участвует, какой результат
- Не используй фразы "В посте говорится", "Автор сообщает" и подобные
- Если пост рекламный — кратко опиши суть предложения
- Отвечай ТОЛЬКО текстом summary, без кавычек и пояснений"""

    response = await call_llm_async(prompt, session, max_tokens=200)
    if not response:
        return ""

    # Очистка ответа
    summary = response.strip().strip('"').strip("'")
    summary = re.sub(r'^```.*?```$', '', summary, flags=re.DOTALL).strip()
    summary = ' '.join(summary.split())

    if len(summary) > 300:
        summary = summary[:297] + "..."

    return summary


async def process_post_with_llm(post: dict, categories: list, session: aiohttp.ClientSession) -> dict | None:
    """Полная обработка одного поста: категоризация + summary + сохранение в БД."""
    post_id = post.get('id')
    post_text = post.get('content_text', '')

    if not post_text or len(post_text.strip()) < 30:
        print(f"  ⏭️ Пост {post_id} слишком короткий, пропуск")
        mark_post_processed(post_id, extract_title(post_text), "")
        return None

    try:
        # Параллельно: категоризация + генерация summary
        cat_task = categorize_post(post_text, categories, session)
        sum_task = generate_summary(post_text, session)
        post_categories, summary = await asyncio.gather(cat_task, sum_task)

        title = extract_title(post_text)

        # Сохранение в БД
        mark_post_processed(post_id, title, summary)
        if post_categories:
            save_post_categories(post_id, post_categories)

        channel_info = post.get('news_channels', {})
        channel_name = channel_info.get('title') or channel_info.get('username') or '?'
        cat_names = []
        if post_categories:
            cat_id_to_name = {c['id']: c['name'] for c in categories}
            cat_names = [cat_id_to_name.get(pc['category_id'], '?') for pc in post_categories]

        print(f"  ✅ Пост {post_id} (@{channel_name}): {len(post_categories)} кат., summary {len(summary)} сим.")

        return {
            'post_id': post_id,
            'title': title,
            'summary': summary,
            'categories': post_categories,
            'category_names': cat_names,
        }
    except Exception as e:
        print(f"  ❌ Ошибка обработки поста {post_id}: {e}")
        return None

# ============================================================================
# ГЕНЕРАЦИЯ PDF-ДАЙДЖЕСТА
# ============================================================================

def generate_news_digest_pdf(digest_date: str, period_start: datetime, period_end: datetime,
                              posts_by_category: list, channels_count: int) -> str:
    """Генерация PDF-дайджеста новостей, сгруппированных по категориям.

    posts_by_category: list of (category_info_dict, posts_list) tuples.
    """
    filename = f"/tmp/news_digest_{digest_date}.pdf"

    doc = SimpleDocTemplate(filename, pagesize=A4,
                            rightMargin=15*mm, leftMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)

    font_regular = FONT_NAME
    font_bold = f"{FONT_NAME}-Bold" if FONT_NAME == 'DejaVuSans' else 'Helvetica-Bold'

    styles = {
        'title': ParagraphStyle('Title', fontName=font_bold, fontSize=16, spaceAfter=8, alignment=1),
        'subtitle': ParagraphStyle('Subtitle', fontName=font_regular, fontSize=10, spaceAfter=12,
                                   alignment=1, textColor=colors.grey),
        'section': ParagraphStyle('Section', fontName=font_bold, fontSize=13, spaceBefore=16,
                                  spaceAfter=8, textColor=colors.HexColor('#2c5aa0')),
        'post_title': ParagraphStyle('PostTitle', fontName=font_bold, fontSize=10, spaceBefore=10,
                                     spaceAfter=2),
        'summary': ParagraphStyle('Summary', fontName=font_regular, fontSize=9, spaceAfter=2,
                                  leading=12, leftIndent=10),
        'meta': ParagraphStyle('Meta', fontName=font_regular, fontSize=8, spaceAfter=2,
                               leftIndent=10, textColor=colors.HexColor('#666666')),
        'link': ParagraphStyle('Link', fontName=font_regular, fontSize=8, spaceAfter=8,
                               leftIndent=10, textColor=colors.HexColor('#2c5aa0')),
        'separator': ParagraphStyle('Separator', fontName=font_regular, fontSize=5,
                                     spaceAfter=6, textColor=colors.HexColor('#cccccc')),
    }

    content = []

    # Заголовок
    content.append(Paragraph("Дайджест новостей отрасли", styles['title']))

    period_str = f"{period_start.strftime('%d.%m.%Y')} — {period_end.strftime('%d.%m.%Y')}"
    content.append(Paragraph(f"Период: {period_str}", styles['subtitle']))

    # Статистика
    total_posts = sum(len(posts) for _, posts in posts_by_category)
    total_categories = len(posts_by_category)
    stats = f"📊 Каналов: {channels_count} | 📝 Новостей: {total_posts} | 📂 Категорий: {total_categories}"
    content.append(Paragraph(stats, styles['subtitle']))
    content.append(Spacer(1, 10))

    # Категории, отсортированные по sort_order
    sorted_categories = sorted(posts_by_category, key=lambda x: x[0].get('sort_order', 999))

    post_number = 0

    for category_info, posts in sorted_categories:
        if not posts:
            continue

        cat_name = category_info.get('name', 'Без категории')
        cat_color = category_info.get('color', '#2c5aa0')
        cat_icon = CATEGORY_ICONS.get(cat_name, DEFAULT_CATEGORY_ICON)

        section_title = f"{cat_icon}  {cat_name.upper()} ({len(posts)})"
        section_color = colors.HexColor(cat_color) if cat_color else colors.HexColor('#2c5aa0')
        content.append(Paragraph(section_title, ParagraphStyle(
            f'Section_{cat_name}', parent=styles['section'],
            textColor=section_color
        )))
        content.append(Paragraph("─" * 80, styles['separator']))

        # Посты внутри категории — сортировка по confidence (убывание)
        sorted_posts = sorted(posts, key=lambda p: p.get('confidence', 0), reverse=True)

        for post in sorted_posts:
            post_number += 1
            title = post.get('title', 'Без заголовка')
            summary = post.get('summary', '')
            post_url = post.get('post_url', '')
            channel_title = post.get('channel_title', '')
            post_date = post.get('post_date', '')
            views = post.get('views_count', 0)

            # Заголовок поста с номером (кликабельный если есть URL)
            if post_url:
                title_text = f"{post_number}. <a href='{post_url}' color='#1a1a1a'><b>{title}</b></a>"
            else:
                title_text = f"{post_number}. <b>{title}</b>"
            content.append(Paragraph(title_text, styles['post_title']))

            # Краткое содержание
            if summary:
                content.append(Paragraph(summary, styles['summary']))

            # Мета: источник, дата, просмотры
            meta_parts = []
            if channel_title:
                meta_parts.append(channel_title)
            if post_date:
                if isinstance(post_date, str):
                    try:
                        dt = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
                        meta_parts.append(dt.strftime('%d.%m.%Y %H:%M'))
                    except ValueError:
                        meta_parts.append(post_date)
                else:
                    meta_parts.append(post_date.strftime('%d.%m.%Y %H:%M'))
            if views:
                meta_parts.append(f"{views} views")

            if meta_parts:
                content.append(Paragraph(" | ".join(meta_parts), styles['meta']))

            # Ссылка на пост (отдельной строкой)
            if post_url:
                short_url = post_url.replace('https://', '')
                content.append(Paragraph(
                    f"<a href='{post_url}' color='#2c5aa0'>{short_url}</a>",
                    styles['link']
                ))

    # Если нет постов вообще
    if total_posts == 0:
        content.append(Paragraph("За указанный период новых публикаций не обнаружено.", styles['subtitle']))

    doc.build(content)
    print(f"✅ PDF дайджест создан: {filename}")
    return filename


# ============================================================================
# ОРКЕСТРАЦИЯ
# ============================================================================

async def run_news_monitoring_async():
    """Главная функция: сканирование каналов → LLM-обработка → PDF-дайджест → Telegram."""
    print("🚀 Запуск мониторинга новостей...")
    start_time = time.time()

    # 1. Инициализация семафоров
    init_semaphores()

    # 2. Уведомление о старте
    send_telegram_message("🚀 <b>Запуск мониторинга новостей</b>\n📰 Сканирование Telegram-каналов...")

    # 3. Загрузка каналов из БД
    channels = get_active_channels()
    if not channels:
        send_telegram_message("❌ Нет активных каналов для мониторинга")
        print("❌ Нет активных каналов")
        return

    print(f"📋 Загружено каналов: {len(channels)}")

    # 4. Загрузка категорий из БД
    categories = get_categories()
    if not categories:
        send_telegram_message("❌ Нет категорий в БД")
        print("❌ Нет категорий")
        return

    print(f"📂 Загружено категорий: {len(categories)}")

    # 5. Расчёт периода
    period_end = datetime.now()
    period_start = period_end - timedelta(days=NEWS_PERIOD_DAYS)
    current_date = period_end.strftime("%Y-%m-%d")
    print(f"📅 Период: {period_start.strftime('%d.%m.%Y')} — {period_end.strftime('%d.%m.%Y')}")

    # === ФАЗА 1: СКАНИРОВАНИЕ КАНАЛОВ ===
    print("\n" + "=" * 60)
    print("ФАЗА 1: СКАНИРОВАНИЕ КАНАЛОВ")
    print("=" * 60)

    total_new_posts = 0
    channels_scanned = 0
    channels_with_errors = 0
    processed_count = 0
    digest_posts = []
    pdf_path = None
    digest_id = None

    # 6. Запуск Playwright
    connector = aiohttp.TCPConnector(limit=5, ssl=False)

    async with aiohttp.ClientSession(connector=connector) as http_session:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                    '--disable-blink-features=AutomationControlled',
                ]
            )

            browser_context = await browser.new_context(
                user_agent=get_random_user_agent(),
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True,
                locale='ru-RU',
                timezone_id='Europe/Moscow',
                extra_http_headers={
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                }
            )

            # 7. Последовательное сканирование каналов
            for i, channel in enumerate(channels, start=1):
                channel_id = channel['id']
                username = channel['username']
                last_message_id = channel.get('last_message_id')

                print(f"\n📡 [{i}/{len(channels)}] Сканирование @{username} (last_id: {last_message_id})...")

                try:
                    posts = await fetch_channel_posts(
                        channel_username=username,
                        browser_context=browser_context,
                        after_message_id=last_message_id,
                        max_posts=MAX_POSTS_PER_CHANNEL,
                    )

                    if posts:
                        saved_count = 0
                        max_msg_id = last_message_id or 0

                        for post_data in posts:
                            post_id = save_post(channel_id, post_data)
                            if post_id:
                                saved_count += 1
                            if post_data['message_id'] > max_msg_id:
                                max_msg_id = post_data['message_id']

                        # Обновление last_message_id
                        if max_msg_id > (last_message_id or 0):
                            update_channel_after_scan(channel_id, max_msg_id)

                        total_new_posts += saved_count
                        print(f"  ✅ Найдено {len(posts)} постов, сохранено {saved_count}, max_id={max_msg_id}")
                    else:
                        print(f"  ℹ️ Новых постов нет")

                    channels_scanned += 1
                except Exception as e:
                    print(f"  ❌ Ошибка сканирования @{username}: {e}")
                    channels_with_errors += 1

                # Пауза между каналами
                if i < len(channels):
                    await asyncio.sleep(DELAY_BETWEEN_CHANNELS)

            # 8. Закрытие браузера
            await browser_context.close()
            await browser.close()

        print(f"\n📊 Фаза 1 завершена: {channels_scanned} каналов, {total_new_posts} новых постов, {channels_with_errors} ошибок")

        # === ФАЗА 2: LLM-ОБРАБОТКА ===
        print("\n" + "=" * 60)
        print("ФАЗА 2: LLM-ОБРАБОТКА")
        print("=" * 60)

        # 9. Получение необработанных постов
        unprocessed = get_unprocessed_posts(period_start)
        print(f"📝 Необработанных постов: {len(unprocessed)}")

        if unprocessed:
            # 10. Параллельная обработка через asyncio.gather + llm_semaphore
            tasks = [
                process_post_with_llm(post, categories, http_session)
                for post in unprocessed
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    print(f"  ❌ Исключение при обработке: {result}")
                elif result is not None:
                    processed_count += 1

        print(f"✅ Обработано LLM: {processed_count} из {len(unprocessed)}")

        # === ФАЗА 3: ДАЙДЖЕСТ ===
        print("\n" + "=" * 60)
        print("ФАЗА 3: ГЕНЕРАЦИЯ ДАЙДЖЕСТА")
        print("=" * 60)

        # 11. Получение постов для дайджеста
        digest_posts = get_posts_for_digest(period_start, period_end)
        print(f"📰 Постов для дайджеста: {len(digest_posts)}")

        if digest_posts:
            # Группировка по категориям: dict[category_id → {'info': dict, 'posts': list}]
            grouped = {}

            for post in digest_posts:
                post_categories = post.get('news_post_categories', [])
                if not post_categories:
                    continue

                for pc in post_categories:
                    cat_info_raw = pc.get('news_categories', {})
                    if not cat_info_raw or not cat_info_raw.get('is_visible', True):
                        continue

                    cat_id = cat_info_raw['id']

                    if cat_id not in grouped:
                        grouped[cat_id] = {
                            'info': {
                                'id': cat_id,
                                'name': cat_info_raw['name'],
                                'color': cat_info_raw.get('color', '#2c5aa0'),
                                'sort_order': cat_info_raw.get('sort_order', 999),
                            },
                            'posts': [],
                        }

                    channel_info = post.get('news_channels', {})
                    post_entry = {
                        'title': post.get('title', ''),
                        'summary': post.get('summary', ''),
                        'post_url': post.get('post_url', ''),
                        'channel_title': channel_info.get('title') or channel_info.get('username', ''),
                        'post_date': post.get('post_date', ''),
                        'views_count': post.get('views_count', 0),
                        'confidence': pc.get('confidence', 0),
                    }

                    # Дедупликация по post_url внутри категории
                    existing_urls = {p['post_url'] for p in grouped[cat_id]['posts']}
                    if post_entry['post_url'] not in existing_urls:
                        grouped[cat_id]['posts'].append(post_entry)

            # Формат для PDF: list[(cat_info_dict, posts_list)]
            posts_by_category = [
                (g['info'], g['posts']) for g in grouped.values()
            ]

            # 12. Генерация PDF
            pdf_path = generate_news_digest_pdf(
                digest_date=current_date,
                period_start=period_start,
                period_end=period_end,
                posts_by_category=posts_by_category,
                channels_count=len(channels),
            )

            # 13. Сохранение дайджеста в БД
            all_post_ids = [p.get('id') for p in digest_posts if p.get('id')]
            total_digest_posts = sum(len(posts) for _, posts in posts_by_category)

            digest_data = {
                'digest_date': current_date,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'total_posts': total_digest_posts,
                'total_channels': len(channels),
                'total_categories': len(posts_by_category),
            }
            digest_id = save_digest(digest_data, all_post_ids)

    # Итоговая статистика
    elapsed = int(time.time() - start_time)
    print(f"\n⏱️ Время выполнения: {elapsed} сек")

    # 14. Отправка PDF + сводного сообщения в Telegram
    total_digest = len(digest_posts) if digest_posts else 0

    summary_msg = f"""📊 <b>Мониторинг новостей завершён</b>

📅 Период: {period_start.strftime('%d.%m.%Y')} — {period_end.strftime('%d.%m.%Y')}
⏱️ Время: {elapsed} сек

📡 Каналов просканировано: <b>{channels_scanned}</b> из {len(channels)}
📝 Новых постов загружено: <b>{total_new_posts}</b>
🤖 Обработано LLM: <b>{processed_count}</b>
📰 Постов в дайджесте: <b>{total_digest}</b>"""

    if channels_with_errors:
        summary_msg += f"\n⚠️ Ошибки сканирования: <b>{channels_with_errors}</b>"

    if pdf_path and os.path.exists(pdf_path):
        summary_msg += "\n\n📎 Подробный дайджест во вложении"
        send_telegram_document(pdf_path, summary_msg)

        # 15. Удаление временных файлов
        try:
            os.remove(pdf_path)
            print(f"🗑️ Временный файл удалён: {pdf_path}")
        except OSError:
            pass
    else:
        if total_digest == 0:
            summary_msg += "\n\nℹ️ За указанный период новых публикаций не обнаружено."
        send_telegram_message(summary_msg)

    # 16. Уведомление о завершении
    print(f"\n✅ Мониторинг новостей завершён за {elapsed} сек")


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

if __name__ == "__main__":
    asyncio.run(run_news_monitoring_async())
