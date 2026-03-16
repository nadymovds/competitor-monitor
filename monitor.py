# -*- coding: utf-8 -*-

# Отключаем предупреждения о небезопасных SSL соединениях
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Импорты
import os
import requests
import hashlib
import json
import uuid
import re
import aiohttp
import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from supabase import create_client, Client
from bs4 import BeautifulSoup
import time

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
_group_ids_raw = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "")
TELEGRAM_GROUP_CHAT_IDS = [i.strip() for i in _group_ids_raw.split(",") if i.strip()]
BOT_URL = os.environ.get("BOT_URL")
TEST_MODE = False  # переопределяется через --test

LLM_MODEL = "llama-3.1-8b-instant"
LLM_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# === ТАЙМАУТЫ И RETRY ===
REQUEST_TIMEOUT = 45
PLAYWRIGHT_TIMEOUT = 45000
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]

MIN_CONTENT_LENGTH = 200

# === СТРАТЕГИЯ ЗАГРУЗКИ ===
USE_PLAYWRIGHT_FIRST = True

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

USER_AGENT = USER_AGENTS[0]

MAX_CONCURRENT_REQUESTS = 15
MAX_CONCURRENT_BROWSER = 8
MAX_CONCURRENT_LLM = 2

# Batch-обработка для стабильности
BATCH_SIZE = 50
BATCH_DELAY = 3  # секунд между батчами

CATEGORY_PRODUCTS = "products"
CATEGORY_PRICES = "prices"
CATEGORY_NEWS = "news"
CATEGORY_TECHNICAL = "technical"
CATEGORY_SERVICES = "services"
CATEGORY_PROMOTION = "promotion"
CATEGORY_OTHER = "other"

# === TELEGRAM CHANNEL SCANNING ===
TG_PLAYWRIGHT_TIMEOUT = 30000
MAX_POSTS_PER_CHANNEL_COMPETITOR = 30
DELAY_BETWEEN_TG_CHANNELS = 3
MAX_CONCURRENT_LLM_TG = 1
TG_SCAN_PERIOD_DAYS = 8

TAGS = {
    "новый_продукт": "#4CAF50",
    "оборудование": "#2196F3",
    "тахографы": "#9C27B0",
    "мониторинг": "#00BCD4",
    "ПО": "#607D8B",
    "акция": "#FF9800",
    "скидка": "#F44336",
    "новая_цена": "#E91E63",
    "бесплатно": "#8BC34A",
    "новость": "#3F51B5",
    "важное": "#f44336",
    "партнёрство": "#009688",
    "законодательство": "#795548",
    "обновление_сайта": "#9E9E9E",
    "wialon": "#FF5722",
    "глонасс": "#673AB7",
}

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

http_semaphore = None
browser_semaphore = None
llm_semaphore = None

def init_semaphores():
    global http_semaphore, browser_semaphore, llm_semaphore
    http_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    browser_semaphore = asyncio.Semaphore(MAX_CONCURRENT_BROWSER)
    llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

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
print("✅ Конфигурация загружена")

# ============================================================================
# TELEGRAM
# ============================================================================

def wake_up_bot(timeout: int = 90) -> None:
    """Пингует Render-сервис, чтобы разбудить его до отправки кнопки."""
    if not BOT_URL:
        return
    try:
        print(f"⏳ Прогрев бота: {BOT_URL} ...")
        requests.get(BOT_URL, timeout=timeout)
        print("✅ Бот проснулся")
    except Exception as e:
        print(f"⚠️ Прогрев бота не удался: {e}")

def get_notification_recipients() -> list:
    if TEST_MODE:
        print("⚠️ TEST MODE: уведомления только администратору")
        return [TELEGRAM_CHAT_ID] if TELEGRAM_CHAT_ID else []
    recipients = []
    for chat_id in ([TELEGRAM_CHAT_ID] if TELEGRAM_CHAT_ID else []) + TELEGRAM_GROUP_CHAT_IDS:
        if chat_id:
            recipients.append(chat_id)
    try:
        result = supabase.table("users").select("telegram_id").execute()
        for row in result.data or []:
            tid = str(row["telegram_id"])
            if tid not in recipients:
                recipients.append(tid)
    except:
        pass
    return recipients

def send_telegram_message(message: str, reply_markup: dict = None) -> bool:
    success = False
    chat_ids = get_notification_recipients()
    for chat_id in chat_ids:
        if chat_id:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
                if reply_markup:
                    payload["reply_markup"] = json.dumps(reply_markup)
                requests.post(url, json=payload, timeout=30)
                success = True
            except:
                pass
    return success

def send_telegram_document(file_path: str, caption: str = "", reply_markup: dict = None) -> bool:
    success = False
    chat_ids = get_notification_recipients()
    for chat_id in chat_ids:
        if chat_id:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
                with open(file_path, 'rb') as f:
                    data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
                    if reply_markup:
                        data['reply_markup'] = json.dumps(reply_markup)
                    requests.post(url, data=data, files={'document': f}, timeout=60)
                success = True
            except:
                pass
    return success

def send_app_button(chat_id: str = None) -> bool:
    """Отправляет кнопку для открытия Mini App"""
    if not TELEGRAM_BOT_TOKEN:
        return False
    target_chat_id = chat_id or (TELEGRAM_GROUP_CHAT_IDS[0] if TELEGRAM_GROUP_CHAT_IDS else None)
    if not target_chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        keyboard = {
            "inline_keyboard": [[{
                "text": "📊 Открыть бота",
                "url": "https://t.me/skai_compit_bot"
            }]]
        }
        requests.post(url, json={
            "chat_id": target_chat_id,
            "text": "🔗 <b>Competitor Monitor</b>\n\nОткройте бота и нажмите кнопку меню слева от поля ввода.",
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }, timeout=30)
        return True
    except:
        return False

# ============================================================================
# УТИЛИТЫ
# ============================================================================

def generate_unique_id(prefix: str = "") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique = str(uuid.uuid4())[:8]
    return f"{prefix}{timestamp}_{unique}" if prefix else f"{timestamp}_{unique}"

def calculate_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def normalize_content_for_hash(content: str) -> str:
    content = re.sub(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', '', content)
    content = re.sub(r'\d{4}-\d{2}-\d{2}', '', content)
    content = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', '', content)
    content = re.sub(r'202[0-9]|203[0-9]', '', content)
    content = re.sub(r'посетител\w*\s*:?\s*\d+', '', content, flags=re.IGNORECASE)
    content = re.sub(r'онлайн\s*:?\s*\d+', '', content, flags=re.IGNORECASE)
    content = ' '.join(content.split())
    return content

# === УТИЛИТЫ ДЛЯ TELEGRAM КАНАЛОВ ===

def clean_tg_post_text(html_text: str) -> str:
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, 'lxml')
    text = soup.get_text(separator='\n', strip=True)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def parse_tg_views_count(views_str: str) -> int:
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

def extract_tg_title(text: str) -> str:
    if not text:
        return ""
    first_line = text.strip().split('\n')[0].strip()
    if len(first_line) > 100:
        first_line = first_line[:97] + "..."
    return first_line

# === ПАРСИНГ TELEGRAM КАНАЛОВ (t.me/s/) ===

async def fetch_tg_channel_page(channel_username: str, browser_context, before_id: int = None) -> str:
    """Загружает HTML страницы публичного Telegram-канала через Playwright."""
    url = f"https://t.me/s/{channel_username}"
    if before_id:
        url += f"?before={before_id}"

    async with browser_semaphore:
        page = await browser_context.new_page()
        try:
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

            await page.route("**/*.{mp4,webm,mp3,wav,avi,mov,flv}", lambda route: route.abort())
            await page.route("**/*google-analytics*", lambda route: route.abort())
            await page.route("**/*googletagmanager*", lambda route: route.abort())
            await page.route("**/*mc.yandex*", lambda route: route.abort())

            await page.goto(url, wait_until='domcontentloaded', timeout=TG_PLAYWRIGHT_TIMEOUT)

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


def parse_tg_posts_from_html(html: str, channel_username: str) -> list:
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

            data_post = message_div.get('data-post', '')
            if '/' not in data_post:
                continue
            message_id = int(data_post.split('/')[-1])

            text_div = message_div.find('div', class_='tgme_widget_message_text')
            raw_html = str(text_div) if text_div else ""
            text = clean_tg_post_text(raw_html)

            time_tag = message_div.find('time')
            post_date = None
            if time_tag and time_tag.get('datetime'):
                post_date = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))

            views_span = message_div.find('span', class_='tgme_widget_message_views')
            views = parse_tg_views_count(views_span.get_text() if views_span else "")

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


def _should_include_post(post, after_message_id, min_date):
    """Проверяет, нужно ли включить пост по message_id или дате."""
    if after_message_id and post['message_id'] > after_message_id:
        return True
    if min_date and post.get('post_date') and post['post_date'] >= min_date:
        return True
    if not after_message_id and not min_date:
        return True
    return False


async def fetch_tg_channel_posts(channel_username: str, browser_context,
                                  after_message_id: int = None,
                                  min_date=None,
                                  max_posts: int = MAX_POSTS_PER_CHANNEL_COMPETITOR) -> list:
    """Загружает новые посты канала с пагинацией через ?before=."""
    all_posts = []
    before_id = None

    while len(all_posts) < max_posts:
        html = await fetch_tg_channel_page(channel_username, browser_context, before_id=before_id)
        if not html:
            break

        page_posts = parse_tg_posts_from_html(html, channel_username)
        if not page_posts:
            break

        total_on_page = len(page_posts)

        page_posts = [p for p in page_posts if _should_include_post(p, after_message_id, min_date)]

        if not page_posts:
            break

        all_posts.extend(page_posts)

        if total_on_page < 10:
            break

        oldest_post = min(page_posts, key=lambda p: p['message_id'])
        oldest_id = oldest_post['message_id']
        oldest_date = oldest_post.get('post_date')

        # Останавливаем пагинацию только если старейший пост старше и по ID, и по дате
        id_exhausted = after_message_id and oldest_id <= after_message_id
        date_exhausted = min_date and oldest_date and oldest_date < min_date
        if id_exhausted and date_exhausted:
            break
        if id_exhausted and not min_date:
            break
        if date_exhausted and not after_message_id:
            break

        before_id = oldest_id
        await asyncio.sleep(1)

    all_posts.sort(key=lambda p: p['message_id'])
    return all_posts[:max_posts]

def clean_html_content(soup: BeautifulSoup) -> str:
    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'iframe']):
        element.decompose()
    text = soup.get_text(separator=' ', strip=True)
    return ' '.join(text.split())

def is_protection_page(content: str) -> bool:
    patterns = [
        'cloudflare', 'ray id', 'checking your browser', 'ddos protection',
        'just a moment', 'attention required', 'security check',
        'recaptcha', 'hcaptcha', 'verifying you are human',
        'защита от ботов', 'проверка браузера',
    ]
    content_lower = content.lower()
    for pattern in patterns:
        if pattern in content_lower:
            return True
    return False

def is_unreadable_content(content: str) -> bool:
    if not content:
        return True
    if len(content) < 50:
        return True
    binary_chars = sum(1 for c in content[:500] if ord(c) < 32 and c not in '\n\r\t')
    if binary_chars > 10:
        return True
    words = re.findall(r'[а-яА-ЯёЁa-zA-Z]{2,}', content[:3000])
    if len(words) < 5:
        return True
    return False

def is_content_insufficient(content: str) -> bool:
    if len(content) < MIN_CONTENT_LENGTH:
        return True
    spa_patterns = ['<div id="root"></div>', '<div id="app"></div>']
    if len(content) < 400:
        for pattern in spa_patterns:
            if pattern.lower() in content.lower():
                return True
    return False

print("✅ Утилиты загружены")

# ============================================================================
# ЗАГРУЗКА КОНТЕНТА
# ============================================================================

def get_headers_for_url(url: str, attempt: int = 0) -> dict:
    user_agent = USER_AGENTS[attempt % len(USER_AGENTS)] if attempt > 0 else get_random_user_agent()
    
    from urllib.parse import urlparse
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    if attempt > 0:
        headers['Referer'] = base_url + '/'
        headers['Origin'] = base_url
    
    return headers


async def fetch_with_aiohttp(url: str, session: aiohttp.ClientSession) -> Tuple[Optional[str], str]:
    """Асинхронная загрузка через aiohttp"""
    
    last_error = "ошибка"
    
    for attempt in range(MAX_RETRIES):
        try:
            headers = get_headers_for_url(url, attempt)
            
            async with http_semaphore:
                async with session.get(
                    url, 
                    headers=headers, 
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                    ssl=False,
                    allow_redirects=True,
                    max_redirects=5
                ) as response:
                    
                    if response.status == 403:
                        if attempt < MAX_RETRIES - 1:
                            delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 10
                            await asyncio.sleep(delay)
                            continue
                        return (None, "доступ_запрещён")
                    
                    if response.status == 404:
                        return (None, "не_найден")
                    
                    if response.status >= 500:
                        last_error = "ошибка_сервера"
                        if attempt < MAX_RETRIES - 1:
                            delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 10
                            await asyncio.sleep(delay)
                            continue
                        return (None, "ошибка_сервера")
                    
                    response.raise_for_status()
                    content_bytes = await response.read()
                    
                    for encoding in ['utf-8', 'cp1251', 'latin-1']:
                        try:
                            content = content_bytes.decode(encoding)
                            break
                        except:
                            continue
                    else:
                        content = content_bytes.decode('utf-8', errors='ignore')
                    
                    soup = BeautifulSoup(content, 'lxml')
                    text = clean_html_content(soup)
                    
                    if len(text) >= MIN_CONTENT_LENGTH:
                        return (text, "")
                    
                    last_error = "мало_контента"
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 5
                        await asyncio.sleep(delay)
                        continue
                    
                    return (text if text else None, "мало_контента")
                    
        except asyncio.TimeoutError:
            last_error = "таймаут"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 10
                await asyncio.sleep(delay)
                continue
                
        except aiohttp.ClientConnectorError:
            last_error = "нет_соединения"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 10
                await asyncio.sleep(delay)
                continue
                
        except aiohttp.ClientResponseError:
            last_error = "ошибка"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 5
                await asyncio.sleep(delay)
                continue
                
        except Exception:
            last_error = "ошибка"
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2)
                continue
    
    return (None, last_error)


async def render_with_browser_stealth(url: str, browser_context, attempt: int = 0) -> Tuple[Optional[str], str]:
    """
    Рендеринг через Playwright со stealth-техниками.
    ИСПРАВЛЕНО: убрана агрессивная блокировка ресурсов.
    """
    try:
        async with browser_semaphore:
            page = await browser_context.new_page()
            
            try:
                # === STEALTH НАСТРОЙКИ ===
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
                
                # === МЯГКАЯ блокировка только тяжёлых медиа (НЕ блокируем CSS и шрифты!) ===
                await page.route("**/*.{mp4,webm,mp3,wav,avi,mov,flv}", lambda route: route.abort())
                # Блокируем только аналитику
                await page.route("**/*google-analytics*", lambda route: route.abort())
                await page.route("**/*googletagmanager*", lambda route: route.abort())
                await page.route("**/*mc.yandex*", lambda route: route.abort())
                
                # Случайная задержка
                await asyncio.sleep(random.uniform(0.2, 0.5))
                
                # Пробуем загрузить страницу с разными стратегиями
                load_success = False
                for wait_strategy in ['domcontentloaded', 'load', 'networkidle']:
                    try:
                        await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until=wait_strategy)
                        load_success = True
                        break
                    except Exception as e:
                        if 'timeout' not in str(e).lower():
                            break
                        continue
                
                if not load_success:
                    await page.close()
                    return (None, "таймаут")
                
                # Ждём загрузку динамического контента
                await page.wait_for_timeout(2500)
                
                # Скролл для активации lazy-load
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
                    await page.wait_for_timeout(500)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    await page.wait_for_timeout(500)
                except:
                    pass
                
                # Получаем контент
                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')
                text = clean_html_content(soup)
                
                await page.close()
                
                if len(text) >= MIN_CONTENT_LENGTH:
                    return (text, "")
                else:
                    return (text if text else None, "мало_контента")
                    
            except PlaywrightTimeout:
                try:
                    await page.close()
                except:
                    pass
                return (None, "таймаут")
                
            except Exception as e:
                try:
                    await page.close()
                except:
                    pass
                error_str = str(e).lower()
                if 'net::err_connection' in error_str or 'net::err_name' in error_str:
                    return (None, "нет_соединения")
                return (None, "ошибка")
                
    except Exception:
        return (None, "ошибка")


async def fetch_website_content_async(url: str, session: aiohttp.ClientSession, browser_context=None) -> Tuple[Optional[str], str]:
    """
    Загрузка контента с умным выбором метода.
    """
    
    if USE_PLAYWRIGHT_FIRST and browser_context:
        # Пробуем Playwright с retry
        for attempt in range(2):
            content, error = await render_with_browser_stealth(url, browser_context, attempt)
            
            if content and len(content) >= MIN_CONTENT_LENGTH:
                if not is_protection_page(content):
                    return (content, "")
            
            if error in ["таймаут", "нет_соединения"] and attempt < 1:
                await asyncio.sleep(RETRY_DELAYS[0])
                continue
            
            if content and is_protection_page(content):
                return (None, "cloudflare")
            
            break
        
        # Fallback на aiohttp
        if error and error not in ["cloudflare", "доступ_запрещён"]:
            aio_content, aio_error = await fetch_with_aiohttp(url, session)
            if aio_content and len(aio_content) >= MIN_CONTENT_LENGTH:
                if not is_protection_page(aio_content):
                    return (aio_content, "")
        
        return (content, error)
    
    else:
        content, error = await fetch_with_aiohttp(url, session)
        
        if content and len(content) >= MIN_CONTENT_LENGTH:
            if not is_protection_page(content):
                return (content, "")
        
        should_try_browser = (
            browser_context and 
            (not content or error in ["мало_контента", "таймаут", "доступ_запрещён"])
        )
        
        if content and browser_context:
            if is_protection_page(content):
                should_try_browser = True
        
        if should_try_browser:
            browser_content, browser_error = await render_with_browser_stealth(url, browser_context)
            if browser_content and len(browser_content) >= MIN_CONTENT_LENGTH:
                if not is_protection_page(browser_content):
                    return (browser_content, "")
                else:
                    return (None, "cloudflare")
        
        return (content, error)


print("✅ Загрузка контента настроена")

# ============================================================================
# LLM АНАЛИЗ
# ============================================================================

async def call_llm_async(prompt: str, session: aiohttp.ClientSession, max_tokens: int = 500, system_prompt: str = None) -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    
    for attempt in range(3):
        try:
            async with llm_semaphore:
                async with session.post(LLM_API_URL, headers=headers, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=90)) as response:
                    if response.status == 429:
                        retry_after = int(response.headers.get('retry-after', 10))
                        if retry_after > 60:
                            print(f"   ⚠️ LLM rate limit (429), retry-after={retry_after}с — квота исчерпана, пропуск")
                            return None
                        print(f"   ⚠️ LLM rate limit (429), ждём {retry_after}с (попытка {attempt+1}/3)")
                        await asyncio.sleep(retry_after)
                        continue
                    response.raise_for_status()
                    result = await response.json()
                    content = result['choices'][0]['message']['content'].strip()
                    await asyncio.sleep(2)  # пауза между вызовами для rate limit
                    return content
        except aiohttp.ClientResponseError as e:
            wait_time = 5 * (attempt + 1)
            print(f"   ⚠️ LLM HTTP ошибка {e.status}: {str(e)[:80]} (попытка {attempt+1}/3, ждём {wait_time}с)")
            if attempt < 2:
                await asyncio.sleep(wait_time)
            else:
                return None
        except Exception as e:
            wait_time = 3 * (attempt + 1)
            print(f"   ⚠️ LLM ошибка: {str(e)[:80]} (попытка {attempt+1}/3)")
            if attempt < 2:
                await asyncio.sleep(wait_time)
            else:
                return None
    return None


def parse_llm_json_response(response: str, competitor_name: str, allow_technical: bool = True, is_tg_post: bool = False) -> Dict[str, Any]:
    """
    Парсит JSON-ответ от LLM.

    Args:
        response: Ответ от LLM
        competitor_name: Имя конкурента (для логирования)
        allow_technical: Разрешить категорию "technical" (False для TG-постов)
        is_tg_post: True для TG-постов (пропускает фильтры сайтов)
    """
    default_result = {
        "category": CATEGORY_OTHER,
        "tags": [],
        "summary": "",
        "is_meaningful": False
    }

    if not response:
        return default_result

    json_str = response.strip()
    json_str = re.sub(r'^```json?\s*', '', json_str)
    json_str = re.sub(r'\s*```$', '', json_str)
    json_str = json_str.strip()

    json_match = re.search(r'\{[^{}]*"category"[^{}]*\}', json_str, re.DOTALL)
    if json_match:
        json_str = json_match.group()

    if not json_str.startswith('{'):
        start = json_str.find('{')
        if start != -1:
            json_str = json_str[start:]

    if not json_str.endswith('}'):
        end = json_str.rfind('}')
        if end != -1:
            json_str = json_str[:end+1]

    try:
        result = json.loads(json_str)

        # Валидные категории зависят от allow_technical
        valid_categories = [CATEGORY_PRODUCTS, CATEGORY_PRICES, CATEGORY_NEWS, CATEGORY_SERVICES, CATEGORY_PROMOTION, CATEGORY_OTHER]
        if allow_technical:
            valid_categories.append(CATEGORY_TECHNICAL)

        if result.get("category") not in valid_categories:
            result["category"] = CATEGORY_OTHER

        # Если technical не разрешён, заменяем на other
        if not allow_technical and result.get("category") == CATEGORY_TECHNICAL:
            result["category"] = CATEGORY_OTHER
        
        valid_tags = [t for t in result.get("tags", []) if t in TAGS]
        result["tags"] = valid_tags[:3]
        
        summary = result.get("summary", "")

        # Очищаем summary от артефактов
        summary = re.sub(r'```.*', '', summary)
        summary = re.sub(r'\{.*', '', summary)
        summary = summary.strip()

        # Проверка на мусорные символы (если более 10% непечатных — отклоняем)
        non_printable = sum(1 for c in summary if ord(c) < 32 or ord(c) > 65535)
        if summary and non_printable > len(summary) * 0.1:
            result["is_meaningful"] = False
            result["summary"] = "Ошибка анализа контента"
            result["category"] = CATEGORY_OTHER
            return result

        # Удаляем нерусские/неанглийские символы (оставляем кириллицу, латиницу, цифры, пунктуацию)
        summary = re.sub(r'[^\w\s\d\.,!?;:\-—–()«»"\'№%₽/\\@#&*+=%°]', '', summary, flags=re.UNICODE)

        # Исправляем известные ошибки LLM
        typo_fixes = {
            'болееную': 'более полную',
            'болееная': 'более полная',
            'ảnh hưởng': '',
        }
        for typo, fix in typo_fixes.items():
            summary = summary.replace(typo, fix)

        # Убираем двойные пробелы
        summary = ' '.join(summary.split())

        # Ограничиваем длину
        if len(summary) > 500:
            summary = summary[:497] + '...'

        # Удаляем "водные" фразы из summary
        filler_patterns = [
            r'^В новой версии сайта\s*',
            r'^В обновлённой версии сайта\s*',
            r'^На сайте компании\s*',
            r'\s*Однако,?\s*эти изменения не связаны напрямую[^.]*\.',
            r'\s*Это единственное изменение между старой и новой версиями сайта\.?',
            r'\s*Остальные изменения не значимы\.?',
            r'\s*Он[аои|] не был[аои]? присутствовал[аои]? в старой версии сайта\.?',
            r'\s*Это указывает на [^.]*\.',
            r'\s*Это свидетельствует о [^.]*\.',
            r'\s*Это говорит о [^.]*\.',
            r'\s*Это может свидетельствовать о [^.]*\.',
            r'\s*Других? значимых изменений не обнаружено\.?',
            r'\s*Других? изменений не выявлено\.?',
            r'\s*Обе версии содержат одинаковый контент[^.]*\.?',
            r'\s*Не обнаружено новых продуктов[^.]*\.?',
            r'\s*Изменения не обнаружены[^.]*\.?',
            r'\s*[Вв]\s*новой версии сайта\s*нет изменений[^.]*\.?',
        ]
        for fp in filler_patterns:
            summary = re.sub(fp, '', summary, flags=re.IGNORECASE)
        summary = summary.strip()

        # Фильтры ниже применяются только к веб-изменениям, не к TG-постам.
        # Для TG-постов доверяем классификации LLM.
        if not is_tg_post:
            # Проверяем на неинформативные ответы
            uninformative_patterns = [
                r'^обновлён\s*(контент|содержимое)?\s*сайт',
                r'^контент\s*сайта\s*(был\s*)?(обновлён|изменён)',
                r'^сайт\s*(был\s*)?(обновлён|изменён)',
                r'^изменения\s*на\s*сайте',
                r'^зафиксированы\s*изменения',
                r'^обнаружены\s*изменения',
                r'^технические\s*изменения',
                r'^незначительные\s*изменения',
                r'^нет\s*значимых\s*изменений',
                r'^нет\s*важных\s*изменений',
                r'^значимых\s*изменений\s*не\s*(обнаружено|выявлено|найдено)',
                r'^изменения\s*коснулись\s*(только\s*)?(контактн|email|телефон|адрес)',
            ]

            summary_lower = summary.lower()
            is_uninformative = False
            for pattern in uninformative_patterns:
                if re.match(pattern, summary_lower):
                    is_uninformative = True
                    break

            if not summary or len(summary) < 40:
                is_uninformative = True

            if is_uninformative:
                result["summary"] = summary if summary else f"Обновлён контент сайта {competitor_name}"
                result["is_meaningful"] = False
                # НЕ меняем категорию - оставляем то, что вернул LLM
                return result

            # Проверка релевантности
            # === ИСКЛЮЧАЕМЫЕ ТЕМЫ (не наша отрасль) ===
            exclude_keywords = [
                # Медицина (розничные услуги)
                'клиник', 'лечен', 'болез', 'пациент', 'врач', 'диагнос', 'медицинск',
                'анализ крови', 'прием врача', 'аптек',
                # Туризм
                'тур', 'отель', 'туристич', 'путешеств', 'отпуск', 'виза',
                # Авиация, ж/д, морской транспорт
                'авиа', 'самолет', 'полет', 'аэропорт', 'железная дорога', 'поезд', 'вагон',
                'корабль', 'судно', 'мор',
                # Социальные программы и развлечение
                'благотворит', 'благодар', 'поздравл', 'праздник', 'юбилей', 'день рожден',
                'развлечен', 'концерт', 'спектакль', 'выставк искусств',
                # Общий PR без конкретики
                'награда', 'рейтинг', 'лучш компани', 'топ компани',
            ]

            summary_lower = summary.lower()
            is_excluded = any(kw in summary_lower for kw in exclude_keywords)

            if is_excluded:
                result["summary"] = summary
                result["is_meaningful"] = False
                print(f"   ⚠️ Исключена по отрасли: {summary[:50]}...")
                return result

            relevant_keywords = [
                # Отраслевые термины
                'транспорт', 'мониторинг', 'глонасс', 'gps', 'трекер',
                'тахограф', 'топлив', 'автопарк', 'навигац', 'телематик',
                'датчик', 'wialon', 'слежен', 'контрол', 'видео',
                # Бизнес-термины
                'цен', 'скидк', 'акци', 'тариф', 'предложени', 'бесплатн',
                'обновлен', 'новый', 'новая', 'новое', 'запуск', 'выпуск',
                'функци', 'возможност', 'интеграц', 'подключ',
                'услуг', 'сервис', 'поддержк', 'обслуживан',
                'партнёр', 'клиент', 'компани',
            ]

            has_relevant = any(kw in summary_lower for kw in relevant_keywords)

            if not has_relevant:
                result["summary"] = summary
                result["is_meaningful"] = False
                print(f"   ⚠️ Нерелевантный контент: {summary[:50]}...")
                return result

        result["summary"] = summary
        result["is_meaningful"] = True

        return result
        
    except json.JSONDecodeError:
        summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', response)
        if summary_match and len(summary_match.group(1)) > 40:
            return {
                "category": CATEGORY_OTHER,
                "tags": [],
                "summary": summary_match.group(1),
                "is_meaningful": True
            }
        return default_result


async def analyze_changes_async(competitor_name: str, new_content: str, session: aiohttp.ClientSession,
                                 previous_content: Optional[str] = None) -> Dict[str, Any]:
    """
    Анализирует изменения на сайте конкурента.
    Если есть previous_content — сравнивает старую и новую версии.
    Если previous_content=None — это первое сканирование, пропускаем.
    """

    # Первое сканирование — нечего сравнивать
    if previous_content is None:
        return {
            "category": CATEGORY_TECHNICAL,
            "tags": [],
            "summary": f"Первое сканирование сайта {competitor_name}",
            "is_meaningful": False,
            "is_first_scan": True
        }

    # Системный промпт — контекст отрасли и правила анализа отделены от контента страниц
    system_prompt = """Ты — аналитик конкурентной разведки. Сравниваешь версии сайтов компаний в сфере ГЛОНАСС/GPS мониторинга транспорта и находишь значимые изменения в их B2B продуктах и услугах для корпоративных автопарков, дорожных перевозчиков и логистических компаний.

ФИКСИРУЙ (is_meaningful: true):
- НОВЫЕ ПРОДУКТЫ/УСЛУГИ: трекеры, тахографы, телематические платформы, видеорегистраторы, мониторинг транспорта
- ОБНОВЛЕНИЯ: новые функции, API, интеграции
- ЦЕНЫ: акции, скидки, тарифы, спецпредложения для корпоративных клиентов
- ПАРТНЁРСТВА: интеграция с логистическими ПО, грузовыми платформами
- НОВОСТИ: сертификация, выставки для транспорта/логистики

ИГНОРИРУЙ (is_meaningful: false):
- Розничные медицинские услуги (клиники, лечение, диагностика)
- Туризм, гражданская авиация, железная дорога, морской транспорт (без связи с автоперевозками)
- Социальные программы, благотворительность, поздравления, праздничный контент
- Технические изменения: дизайн, даты, счётчики без нового контента
- Изменения контактных данных (email, телефон, адрес)
- Общие новости без отношения к B2B продуктам

ТРЕБОВАНИЯ К SUMMARY:
- Начинай сразу с сути: "Добавлен...", "Обновлено...", "Запущена...", "Новый..."
- Называй конкретные продукты, модели, цены, функции — то, что буквально написано на сайте
- Запрещено упоминать версии сайта, структуру страниц, навигацию
- Только факты из изменённого контента. Без выводов и оценок. Максимум 2-3 предложения
- Если нет значимых изменений — пустая строка ""

ТЕГИ — выбирай только те, что точно соответствуют найденным изменениям.
Если изменение про новый продукт, а не про цену — теги "акция" и "скидка" не нужны.
Допустимые значения: новый_продукт, оборудование, тахографы, мониторинг, ПО, акция, скидка, новая_цена, бесплатно, новость, важное, партнёрство, законодательство, wialon, глонасс

КАТЕГОРИИ (выбери одну):
- "products" — новый продукт, устройство, трекер, тахограф, ПО, платформа, обновление функций
- "prices" — акция, скидка, спецпредложение, изменение цен/тарифов
- "news" — партнёрство, мероприятие, сертификация, важное объявление
- "technical" — только дизайн/структура без нового контента

Отвечай ТОЛЬКО на русском языке. Формат ответа — только JSON, без пояснений:
{"category": "...", "summary": "...", "tags": [...], "is_meaningful": true/false}"""

    # Пользовательский промпт — только контент страниц, обёрнутый в XML-теги
    prompt = f"""Компания: "{competitor_name}"

<old_version>
{previous_content[:3000]}
</old_version>

<new_version>
{new_content[:3000]}
</new_version>

Что конкретно изменилось между версиями?"""

    response = await call_llm_async(prompt, session, max_tokens=600, system_prompt=system_prompt)
    return parse_llm_json_response(response, competitor_name)


async def analyze_tg_post_async(competitor_name: str, post_text: str,
                                 session: aiohttp.ClientSession) -> Dict[str, Any]:
    """Анализирует пост из Telegram-канала конкурента через LLM."""

    if not post_text or len(post_text.strip()) < 20:
        return {
            "category": CATEGORY_OTHER,
            "tags": [],
            "summary": "",
            "is_meaningful": False
        }

    prompt = f"""Проанализируй пост из Telegram-канала компании "{competitor_name}" в сфере ГЛОНАСС/GPS мониторинга транспорта.

ТЕКСТ ПОСТА:
{post_text[:2000]}

ОТРАСЛЬ: Телематика, видеоаналитика, телемедицина и безопасность на КОММЕРЧЕСКОМ ТРАНСПОРТЕ.
ВАЖНО: Отслеживаем B2B услуги для корпоративных автопарков, дорожных перевозчиков и логистических компаний.

ЗАДАЧА: Определи категорию, кратко опиши суть поста. ВСЕГДА пиши summary — даже если пост не очень важный.

ВАЖНО (is_meaningful: true) — посты про:
- Продукты/услуги: новые устройства, трекеры, видеорегистраторы, тахографы, платформы мониторинга, обновления функций, релизы ПО
- Цены/тарифы: акции, скидки, изменение цен, спецпредложения
- Условия обслуживания: SLA, тарифные планы, техподдержка, сбой системы, технические работы
- Партнёрства и интеграции: с логистическим ПО, автопарк-системами, дорожными сервисами
- Новости: выставки, конференции, форумы, сертификация, стандарты, участие в мероприятиях
- Продвижение: маркетинговые посты, кейсы клиентов, демонстрации продукта, промо-видео, обзоры функций, результаты/достижения с продуктом, экономия с продуктом, обучающий контент по продукту

ИГНОРИРУЙ (is_meaningful: false):
- Поздравления с праздниками, мотивационные цитаты
- Благотворительность, социальные программы
- Развлекательный контент без связи с продуктами компании
- Анонсы переезда в другой мессенджер/соцсеть без конкретики о продуктах
- Нерелевантное законодательство (не про транспорт/телематику)
- Посты без текста (только фото/видео без описания)

ПРАВИЛА:
- Отвечай ТОЛЬКО на русском языке
- ВСЕГДА заполняй summary — 1-2 предложения о сути поста
- Если сомневаешься между "other" и другой категорией — выбери другую категорию, если пост хоть как-то связан с продуктами/услугами компании

КАТЕГОРИИ (выбери СТРОГО ОДНУ из шести):
1. "products" — обновление продукта, новая функция, релиз ПО, новый датчик/фильтр, доработка платформы
2. "prices" — акция, скидка, изменение цен/тарифов, спецпредложение, бесплатный период
3. "services" — условия обслуживания, SLA, тарифные планы, техподдержка, сбой системы, технические работы
4. "news" — участие в выставках/конференциях/форумах, партнёрства, сертификация, интеграции, отраслевые новости
5. "promotion" — маркетинг, кейсы, промо-видео, демонстрация продукта, обзоры, обучающие материалы, результаты/экономия клиентов
6. "other" — ТОЛЬКО для действительно нерелевантного контента (поздравления, мотивация, переезд в другой мессенджер)

ФОРМАТ ОТВЕТА (только JSON, без пояснений):
{{
    "category": "products|prices|services|news|promotion|other",
    "summary": "Краткое описание сути поста. 1-2 предложения.",
    "tags": ["тег1", "тег2"],
    "is_meaningful": true/false
}}

ТЕГИ: новый_продукт, видео, мониторинг, тахографы, платформа, акция, скидка, интеграция, обновление, партнёрство, сбой, выставка, кейс, промо"""

    response = await call_llm_async(prompt, session, max_tokens=400)
    # allow_technical=False - TG посты не должны получать категорию "technical"
    # is_tg_post=True - пропускаем фильтры сайтов (uninformative patterns, keyword relevance)
    return parse_llm_json_response(response, competitor_name, allow_technical=False, is_tg_post=True)

print("✅ LLM анализ настроен")

# ============================================================================
# PDF ГЕНЕРАЦИЯ — ИСПРАВЛЕННАЯ С КЛИКАБЕЛЬНЫМИ ССЫЛКАМИ
# ============================================================================

def generate_pdf_report(
    report_date: str,
    total_competitors: int,
    total_urls: int,
    categorized_changes: Dict[str, List[Dict]],
    failed_sites: List[Dict],
    duplicates_count: int = 0,
    first_scans_count: int = 0,
    tg_posts_count: int = 0
) -> str:
    filename = f"/tmp/competitor_report_{report_date}.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=A4,
                           rightMargin=15*mm, leftMargin=15*mm,
                           topMargin=15*mm, bottomMargin=15*mm)
    
    font_regular = FONT_NAME
    font_bold = f"{FONT_NAME}-Bold" if FONT_NAME == 'DejaVuSans' else 'Helvetica-Bold'
    
    styles = {
        'title': ParagraphStyle('Title', fontName=font_bold, fontSize=16, spaceAfter=8, alignment=1),
        'subtitle': ParagraphStyle('Subtitle', fontName=font_regular, fontSize=10, spaceAfter=12, alignment=1, textColor=colors.grey),
        'section': ParagraphStyle('Section', fontName=font_bold, fontSize=13, spaceBefore=16, spaceAfter=8, textColor=colors.HexColor('#2c5aa0')),
        'company': ParagraphStyle('Company', fontName=font_bold, fontSize=10, spaceBefore=10, spaceAfter=2),
        'summary': ParagraphStyle('Summary', fontName=font_regular, fontSize=9, spaceAfter=2, leading=12, leftIndent=10),
        'tags': ParagraphStyle('Tags', fontName=font_regular, fontSize=8, spaceAfter=8, leftIndent=10),
        'error': ParagraphStyle('Error', fontName=font_regular, fontSize=8, spaceAfter=2, textColor=colors.HexColor('#666666')),
        'stats': ParagraphStyle('Stats', fontName=font_regular, fontSize=9, spaceAfter=4, leftIndent=10),
        'stats_header': ParagraphStyle('StatsHeader', fontName=font_bold, fontSize=11, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor('#333333')),
    }
    
    content = []
    
    content.append(Paragraph("Отчёт мониторинга конкурентов", styles['title']))
    content.append(Paragraph(f"Дата: {report_date}", styles['subtitle']))

    total_changes = sum(len(v) for k, v in categorized_changes.items() if k not in (CATEGORY_TECHNICAL, CATEGORY_OTHER))
    total_ok = total_urls - len(failed_sites)

    tg_stats = f" | 📱 TG постов: {tg_posts_count}" if tg_posts_count > 0 else ""
    stats = f"📊 Конкурентов: {total_competitors} | 🔗 URL: {total_urls} | ✅ Успешно: {total_ok} | 🔄 Изменения: {total_changes}{tg_stats} | 🔁 Дубликаты: {duplicates_count} | 🆕 Первые: {first_scans_count} | ⚠️ Проблемы: {len(failed_sites)}"
    content.append(Paragraph(stats, styles['subtitle']))
    content.append(Spacer(1, 10))
    
    # === СТАТИСТИКА ПО СТАТУСАМ ===
    if failed_sites:
        by_reason = {}
        for site in failed_sites:
            reason = site.get('error_type', 'другое')
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(site)
        
        content.append(Paragraph("📈 СТАТИСТИКА ПО СТАТУСАМ", styles['stats_header']))

        # Успешные
        success_rate = round(total_ok / total_urls * 100, 1) if total_urls > 0 else 0
        content.append(Paragraph(f"✅ Успешно проверено: <b>{total_ok}</b> ({success_rate}%)", styles['stats']))

        # Дубликаты
        if duplicates_count > 0:
            content.append(Paragraph(f"🔁 Пропущено дубликатов: <b>{duplicates_count}</b>", styles['stats']))

        # Первые сканирования
        if first_scans_count > 0:
            content.append(Paragraph(f"🆕 Первых сканирований: <b>{first_scans_count}</b>", styles['stats']))

        # Группируем статистику
        reason_labels = {
            "cloudflare": ("🛡️ Защита Cloudflare", "#FF9800"),
            "таймаут": ("⏱️ Таймаут", "#F44336"),
            "нет_соединения": ("🔌 Нет соединения", "#9C27B0"),
            "доступ_запрещён": ("🚫 Доступ запрещён", "#E91E63"),
            "не_найден": ("❓ Страница не найдена (404)", "#607D8B"),
            "ошибка_сервера": ("💥 Ошибка сервера (5xx)", "#795548"),
            "нечитаемый": ("📄 Нечитаемый контент", "#9E9E9E"),
            "мало_контента": ("📄 Мало контента", "#BDBDBD"),
            "ошибка": ("⚠️ Другие ошибки", "#757575"),
        }
        
        sorted_reasons = sorted(by_reason.items(), key=lambda x: -len(x[1]))
        for reason, sites in sorted_reasons:
            label, color = reason_labels.get(reason, (reason, "#757575"))
            pct = round(len(sites) / total_urls * 100, 1) if total_urls > 0 else 0
            content.append(Paragraph(f"<font color='{color}'>{label}: <b>{len(sites)}</b> ({pct}%)</font>", styles['stats']))
    
    content.append(Spacer(1, 10))
    
    # === ИЗМЕНЕНИЯ ПО КАТЕГОРИЯМ (с кликабельными ссылками) ===
    sections = [
        (CATEGORY_PRODUCTS, "🏷️ НОВЫЕ ПРОДУКТЫ И УСЛУГИ"),
        (CATEGORY_PRICES, "💰 ЦЕНЫ И АКЦИИ"),
        (CATEGORY_SERVICES, "🛠️ СЕРВИС И ОБСЛУЖИВАНИЕ"),
        (CATEGORY_NEWS, "📰 НОВОСТИ"),
        (CATEGORY_PROMOTION, "📣 ПРОДВИЖЕНИЕ"),
    ]
    
    for category, title in sections:
        items = categorized_changes.get(category, [])
        if not items:
            continue

        content.append(Paragraph(title, styles['section']))

        for i, item in enumerate(items, 1):
            # Используем display_name если доступен (включает label URL)
            name = item.get('display_name') or item.get('competitor', '')
            summary = item.get('summary', '')
            tags = item.get('tags', [])
            is_telegram = item.get('source_type') == 'telegram'

            # Для TG-постов используем post_url, для сайтов — url
            url = item.get('post_url') if is_telegram else item.get('url', '')
            source_prefix = "TG: " if is_telegram else ""

            # === КЛИКАБЕЛЬНАЯ ССЫЛКА ===
            if url:
                # Добавляем https:// если нет
                full_url = url if url.startswith('http') else f'https://{url}'
                company_text = f"{i}. {source_prefix}<b>{name}</b> — <a href='{full_url}' color='blue'>{full_url}</a>"
            else:
                company_text = f"{i}. {source_prefix}<b>{name}</b>"
            content.append(Paragraph(company_text, styles['company']))
            
            if summary:
                content.append(Paragraph(summary, styles['summary']))
            
            if tags:
                tag_parts = [f"<font color='{TAGS.get(tag, '#999')}'><b>#{tag}</b></font>" for tag in tags]
                content.append(Paragraph(" ".join(tag_parts), styles['tags']))
    
    # === ПРОБЛЕМНЫЕ САЙТЫ (ПОЛНЫЙ СПИСОК с кликабельными ссылками) ===
    if failed_sites:
        content.append(Paragraph("⚠️ НЕ УДАЛОСЬ ПРОВЕРИТЬ", styles['section']))
        
        by_reason = {}
        for site in failed_sites:
            reason = site.get('error_type', 'другое')
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(site)
        
        reason_labels = {
            "cloudflare": "🛡️ Защита Cloudflare",
            "таймаут": "⏱️ Таймаут",
            "нет_соединения": "🔌 Нет соединения",
            "доступ_запрещён": "🚫 Доступ запрещён",
            "не_найден": "❓ Страница не найдена",
            "ошибка_сервера": "💥 Ошибка сервера",
            "нечитаемый": "📄 Нечитаемый контент",
            "мало_контента": "📄 Мало контента",
        }
        
        sorted_reasons = sorted(by_reason.items(), key=lambda x: -len(x[1]))
        
        for reason, sites in sorted_reasons:
            label = reason_labels.get(reason, f"❓ {reason}")
            
            # === ПОЛНЫЙ СПИСОК БЕЗ ОГРАНИЧЕНИЙ (все сайты с кликабельными ссылками) ===
            names = []
            for site in sites:
                # Используем display_name если доступен (включает label URL)
                name = site.get('display_name') or site.get('competitor', 'Неизвестный')
                url = site.get('url', '')
                if url:
                    full_url = url if url.startswith('http') else f'https://{url}'
                    names.append(f"<a href='{full_url}' color='blue'>{name}</a>")
                else:
                    names.append(name)
            
            text = f"{label} ({len(sites)}): {', '.join(names)}"
            content.append(Paragraph(text, styles['error']))
    
    doc.build(content)
    print(f"✅ PDF создан: {filename}")
    return filename

print("✅ PDF генерация настроена")

# ============================================================================
# SUPABASE
# ============================================================================

def get_previous_hash(competitor_id: str) -> Optional[str]:
    try:
        competitor = supabase.table('competitors').select('last_scan_id').eq('id', competitor_id).single().execute()
        if not competitor.data or not competitor.data.get('last_scan_id'):
            return None
        scan = supabase.table('scan_results').select('last_hash').eq('id', competitor.data['last_scan_id']).single().execute()
        if scan.data:
            h = scan.data.get('last_hash')
            return None if h in ["PROTECTION_PAGE", "UNREADABLE", "ERROR"] else h
        return None
    except:
        return None

def create_scan_result(scan_id, scan_date, competitor_id, new_hash, content_changed, raw_content="", llm_summary="", report_id=None):
    try:
        data = {
            'scan_id': scan_id, 'scan_date': scan_date, 'competitor_id': competitor_id,
            'last_hash': new_hash, 'content_changed': content_changed,
            'raw_change_data': raw_content[:5000] if raw_content else None,
            'llm_summary': llm_summary or None, 'report_id': report_id
        }
        result = supabase.table('scan_results').insert(data).execute()
        return result.data[0]['id'] if result.data else None
    except:
        return None

def update_competitor_last_scan(competitor_id, scan_result_id):
    try:
        supabase.table('competitors').update({'last_scan_id': scan_result_id}).eq('id', competitor_id).execute()
    except:
        pass

def create_summary_report(report_id, report_date):
    try:
        result = supabase.table('summary_reports').insert({
            'report_id': report_id, 'report_date': report_date, 'overall_llm_report': ''
        }).execute()
        return result.data[0]['id'] if result.data else None
    except:
        return None

def update_summary_report_with_stats(report_id: str, total_sites: int, successful_sites: int, 
                                      changes_count: int, problems_count: int, duration_seconds: int):
    """Обновляет отчёт со статистикой для Mini App"""
    try:
        supabase.table('summary_reports').update({
            'total_sites': total_sites,
            'successful_sites': successful_sites,
            'changes_count': changes_count,
            'problems_count': problems_count,
            'duration_seconds': duration_seconds,
            'overall_llm_report': f"Изменения: {changes_count}"
        }).eq('id', report_id).execute()
    except Exception as e:
        print(f"⚠️ Ошибка обновления статистики: {e}")

def normalize_summary_for_hash(summary: str) -> str:
    """Нормализует summary для вычисления хеша: lowercase, strip, убрать двойные пробелы"""
    normalized = summary.lower().strip()
    normalized = ' '.join(normalized.split())
    return normalized


def check_duplicate_change(competitor_id: str, summary: str) -> bool:
    """
    Проверяет, есть ли дубликат изменения за последние 14 дней.
    Возвращает True если дубликат найден, False если нет.
    """
    try:
        # Здесь теперь ожидаем уже готовый content_hash (sha256 от нормализованного контента)
        content_hash = summary

        # Проверяем наличие записи с таким же content_hash за последние 14 дней
        fourteen_days_ago = (datetime.now() - timedelta(days=14)).isoformat()

        result = supabase.table('changes').select('id').eq('competitor_id', competitor_id).eq('content_hash', content_hash).gt('detected_at', fourteen_days_ago).limit(1).execute()

        return bool(result.data)
    except Exception as e:
        print(f"   ⚠️ Ошибка check_duplicate: {str(e)[:80]}")
        return False


def save_change(competitor_id: str, category: str, summary: str, tags: List[str], report_id: str, content_hash: str, is_meaningful: bool = True) -> bool:
    """
    Сохраняет изменение в таблицу changes используя content_hash для дедупликации.
    Возвращает True если вставлено, False если дубликат или ошибка.
    """
    try:
        data = {
            'competitor_id': competitor_id,
            'detected_at': datetime.now().isoformat(),
            'category': category,
            'summary': summary,
            'tags': tags,
            'content_hash': content_hash,
            'report_id': report_id,
            'is_meaningful': is_meaningful
        }

        result = supabase.table('changes').insert(data).execute()
        return bool(result.data)

    except Exception as e:
        # Проверяем на конфликт уникальности (код 23505 в PostgreSQL)
        error_str = str(e).lower()
        if 'duplicate' in error_str or '23505' in error_str or 'unique' in error_str:
            return False
        # Другая ошибка — логируем, но не падаем
        print(f"   ⚠️ Ошибка save_change: {str(e)[:100]}")
        return False

# ============================================================================
# COMPETITOR HEALTH TRACKING
# ============================================================================

def update_competitor_health_success(competitor_id: str):
    """Обновляет health при успешном сканировании: сбрасывает счётчик ошибок"""
    try:
        data = {
            'competitor_id': competitor_id,
            'consecutive_failures': 0,
            'last_success_at': datetime.now().isoformat(),
            'last_error_type': None
        }
        supabase.table('competitor_health').upsert(data, on_conflict='competitor_id').execute()
    except Exception as e:
        print(f"   ⚠️ Ошибка update_health_success: {str(e)[:80]}")


def update_competitor_health_failure(competitor_id: str, error_type: str):
    """Обновляет health при ошибке: инкрементирует счётчик ошибок"""
    try:
        # Сначала получаем текущее значение
        existing = supabase.table('competitor_health').select('consecutive_failures').eq('competitor_id', competitor_id).execute()

        current_failures = 0
        if existing.data:
            current_failures = existing.data[0].get('consecutive_failures', 0) or 0

        data = {
            'competitor_id': competitor_id,
            'consecutive_failures': current_failures + 1,
            'last_error_type': error_type
        }
        supabase.table('competitor_health').upsert(data, on_conflict='competitor_id').execute()
    except Exception as e:
        print(f"   ⚠️ Ошибка update_health_failure: {str(e)[:80]}")


def get_competitor_health(competitor_id: str) -> Optional[Dict]:
    """Получает данные о здоровье конкурента"""
    try:
        result = supabase.table('competitor_health').select('*').eq('competitor_id', competitor_id).execute()
        return result.data[0] if result.data else None
    except:
        return None


# ============================================================================
# COMPETITOR CONTENT (для сравнения старой и новой версий)
# ============================================================================

MAX_STORED_CONTENT_LENGTH = 30000


def get_previous_content(competitor_id: str) -> Optional[str]:
    """
    Возвращает предыдущий сохранённый контент для конкурента.
    Если записи нет — возвращает None (первое сканирование).
    """
    try:
        result = supabase.table('competitor_content').select('content_text').eq('competitor_id', competitor_id).execute()
        if result.data:
            return result.data[0].get('content_text')
        return None
    except Exception as e:
        print(f"   ⚠️ Ошибка get_previous_content: {str(e)[:80]}")
        return None


def save_current_content(competitor_id: str, content: str, content_hash: str) -> bool:
    """
    Сохраняет текущий контент в таблицу competitor_content (upsert).
    Контент обрезается до MAX_STORED_CONTENT_LENGTH символов.
    """
    try:
        data = {
            'competitor_id': competitor_id,
            'content_text': content[:MAX_STORED_CONTENT_LENGTH],
            'content_hash': content_hash,
            'updated_at': datetime.now().isoformat()
        }
        supabase.table('competitor_content').upsert(data, on_conflict='competitor_id').execute()
        return True
    except Exception as e:
        print(f"   ⚠️ Ошибка save_current_content: {str(e)[:80]}")
        return False


print("✅ Supabase настроен")

# ============================================================================
# URL CONTENT (для сравнения старой и новой версий по URL)
# ============================================================================

def get_previous_content_for_url(url_id: str) -> Optional[str]:
    """
    Возвращает предыдущий сохранённый контент для конкретного URL.
    Если записи нет — возвращает None (первое сканирование).
    """
    try:
        result = supabase.table('url_content').select('content_text').eq('url_id', url_id).execute()
        if result.data:
            return result.data[0].get('content_text')
        return None
    except Exception as e:
        print(f"   ⚠️ Ошибка get_previous_content_for_url: {str(e)[:80]}")
        return None


def save_current_content_for_url(url_id: str, content: str, content_hash: str) -> bool:
    """
    Сохраняет текущий контент в таблицу url_content (upsert).
    Контент обрезается до MAX_STORED_CONTENT_LENGTH символов.
    """
    try:
        data = {
            'url_id': url_id,
            'content_text': content[:MAX_STORED_CONTENT_LENGTH],
            'content_hash': content_hash,
            'updated_at': datetime.now().isoformat()
        }
        supabase.table('url_content').upsert(data, on_conflict='url_id').execute()
        return True
    except Exception as e:
        print(f"   ⚠️ Ошибка save_current_content_for_url: {str(e)[:80]}")
        return False


# ============================================================================
# URL HEALTH TRACKING
# ============================================================================

def update_url_health_success(url_id: str):
    """Обновляет health при успешном сканировании URL: сбрасывает счётчик ошибок"""
    try:
        data = {
            'url_id': url_id,
            'consecutive_failures': 0,
            'last_success_at': datetime.now().isoformat(),
            'last_error_type': None
        }
        supabase.table('url_health').upsert(data, on_conflict='url_id').execute()
    except Exception as e:
        print(f"   ⚠️ Ошибка update_url_health_success: {str(e)[:80]}")


def update_url_health_failure(url_id: str, error_type: str):
    """Обновляет health при ошибке сканирования URL: инкрементирует счётчик ошибок"""
    try:
        # Сначала получаем текущее значение
        existing = supabase.table('url_health').select('consecutive_failures').eq('url_id', url_id).execute()

        current_failures = 0
        if existing.data:
            current_failures = existing.data[0].get('consecutive_failures', 0) or 0

        data = {
            'url_id': url_id,
            'consecutive_failures': current_failures + 1,
            'last_error_type': error_type
        }
        supabase.table('url_health').upsert(data, on_conflict='url_id').execute()
    except Exception as e:
        print(f"   ⚠️ Ошибка update_url_health_failure: {str(e)[:80]}")


# ============================================================================
# DUPLICATE CHECK AND SAVE CHANGE (с поддержкой url_id)
# ============================================================================

def check_duplicate_change_for_url(competitor_id: str, content_hash: str, url_id: str = None) -> bool:
    """
    Проверяет, есть ли дубликат изменения за последние 14 дней для конкретного URL.
    Возвращает True если дубликат найден, False если нет.
    """
    try:
        fourteen_days_ago = (datetime.now() - timedelta(days=14)).isoformat()

        query = supabase.table('changes').select('id').eq('competitor_id', competitor_id).eq('content_hash', content_hash)

        if url_id:
            query = query.eq('url_id', url_id)

        query = query.gt('detected_at', fourteen_days_ago).limit(1)
        result = query.execute()

        return bool(result.data)
    except Exception as e:
        print(f"   ⚠️ Ошибка check_duplicate_for_url: {str(e)[:80]}")
        return False


def save_change_for_url(
    competitor_id: str,
    category: str,
    summary: str,
    tags: List[str],
    report_id: str,
    content_hash: str,
    url_id: str = None,
    scanned_url: str = None,
    is_meaningful: bool = True
) -> bool:
    """
    Сохраняет изменение в таблицу changes с привязкой к URL.
    Возвращает True если вставлено, False если дубликат или ошибка.
    """
    try:
        data = {
            'competitor_id': competitor_id,
            'detected_at': datetime.now().isoformat(),
            'category': category,
            'summary': summary,
            'tags': tags,
            'content_hash': content_hash,
            'report_id': report_id,
            'url_id': url_id,
            'scanned_url': scanned_url,
            'is_meaningful': is_meaningful
        }

        result = supabase.table('changes').insert(data).execute()
        return bool(result.data)

    except Exception as e:
        error_str = str(e).lower()
        if 'duplicate' in error_str or '23505' in error_str or 'unique' in error_str:
            return False
        print(f"   ⚠️ Ошибка save_change_for_url: {str(e)[:100]}")
        return False


print("✅ URL функции настроены")

# ============================================================================
# SUPABASE — TELEGRAM ПОСТЫ КОНКУРЕНТОВ
# ============================================================================

def save_competitor_tg_post(competitor_id: str, url_id: str, channel_username: str,
                            post_data: dict, report_id: str) -> int:
    """Upsert поста в competitor_tg_posts. Возвращает id записи или None."""
    try:
        data = {
            'competitor_id': competitor_id,
            'url_id': url_id,
            'channel_username': channel_username,
            'message_id': post_data['message_id'],
            'post_url': post_data.get('post_url'),
            'content_text': post_data.get('text', ''),
            'title': extract_tg_title(post_data.get('text', '')),
            'post_date': post_data['post_date'].isoformat() if post_data.get('post_date') else None,
            'has_photo': post_data.get('has_photo', False),
            'has_video': post_data.get('has_video', False),
            'has_document': post_data.get('has_document', False),
            'views_count': post_data.get('views', 0),
            'content_hash': post_data.get('content_hash'),
            'report_id': report_id,
        }

        result = supabase.table('competitor_tg_posts').upsert(
            data, on_conflict='channel_username,message_id'
        ).select('id').execute()

        if result.data:
            return result.data[0].get('id')

        # Fallback: получаем id отдельным запросом
        fallback = supabase.table('competitor_tg_posts') \
            .select('id') \
            .eq('channel_username', channel_username) \
            .eq('message_id', post_data['message_id']) \
            .single() \
            .execute()
        if fallback.data:
            return fallback.data.get('id')
        return None

    except Exception as e:
        print(f"   ⚠️ Ошибка save_competitor_tg_post: {str(e)[:100]}")
        return None


def get_existing_tg_content_hashes(competitor_id: str, days: int = 14) -> set:
    """Возвращает set content_hash постов конкурента за последние N дней для дедупликации."""
    try:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        result = supabase.table('competitor_tg_posts') \
            .select('content_hash') \
            .eq('competitor_id', competitor_id) \
            .gte('detected_at', since) \
            .not_.is_('content_hash', 'null') \
            .execute()

        return {row['content_hash'] for row in (result.data or [])}

    except Exception as e:
        print(f"   ⚠️ Ошибка get_existing_tg_content_hashes: {str(e)[:100]}")
        return set()


def mark_tg_post_processed(post_id: int, title: str, summary: str,
                           category: str, tags: list, is_meaningful: bool = False) -> bool:
    """Обновляет пост после LLM-анализа."""
    try:
        data = {
            'title': title,
            'summary': summary,
            'category': category,
            'tags': tags or [],
            'is_processed': True,
        }

        result = supabase.table('competitor_tg_posts') \
            .update(data) \
            .eq('id', post_id) \
            .execute()

        return bool(result.data)

    except Exception as e:
        print(f"   ⚠️ Ошибка mark_tg_post_processed: {str(e)[:100]}")
        return False


def update_competitor_url_last_message_id(url_id: str, last_message_id: int) -> bool:
    """Обновляет last_message_id в competitor_urls для отслеживания позиции сканирования."""
    try:
        result = supabase.table('competitor_urls') \
            .update({'last_message_id': last_message_id}) \
            .eq('id', url_id) \
            .execute()

        return bool(result.data)

    except Exception as e:
        print(f"   ⚠️ Ошибка update_competitor_url_last_message_id: {str(e)[:100]}")
        return False


print("✅ TG функции настроены")

# ============================================================================
# СКАНИРОВАНИЕ URL
# ============================================================================

async def scan_url_async(
    competitor: Dict,
    url_info: Dict,
    report_id: str,
    scan_date: str,
    http_session: aiohttp.ClientSession,
    browser_context
) -> Dict[str, Any]:
    """
    Сканирует один URL конкурента.

    Args:
        competitor: Данные конкурента {id, name, ...}
        url_info: Данные URL {id, url, label, is_active}
        report_id: ID отчёта
        scan_date: Дата сканирования
        http_session: HTTP сессия aiohttp
        browser_context: Контекст браузера Playwright
    """
    competitor_id = competitor['id']
    competitor_name = competitor.get('name', 'Unknown')

    url_id = url_info.get('id')
    url = url_info.get('url', '')
    label = url_info.get('label', '')

    # Формируем отображаемое имя
    display_name = f"{competitor_name} [{label}]" if label else competitor_name

    print(f"🔍 {display_name}: {url}")

    previous_hash = get_previous_hash(competitor_id)

    content, error_type = await fetch_website_content_async(url, http_session, browser_context)

    if not content:
        if url_id:
            update_url_health_failure(url_id, error_type or 'ошибка')
        else:
            update_competitor_health_failure(competitor_id, error_type or 'ошибка')
        return {
            'competitor': competitor_name,
            'display_name': display_name,
            'url': url,
            'url_id': url_id,
            'label': label,
            'error_type': error_type or 'ошибка',
            'is_error': True
        }

    if is_protection_page(content):
        scan_id = generate_unique_id("scan_")
        create_scan_result(scan_id, scan_date, competitor_id, "PROTECTION_PAGE", False)
        if url_id:
            update_url_health_failure(url_id, 'cloudflare')
        else:
            update_competitor_health_failure(competitor_id, 'cloudflare')
        return {
            'competitor': competitor_name,
            'display_name': display_name,
            'url': url,
            'url_id': url_id,
            'label': label,
            'error_type': 'cloudflare',
            'is_error': True
        }

    if is_unreadable_content(content):
        scan_id = generate_unique_id("scan_")
        create_scan_result(scan_id, scan_date, competitor_id, "UNREADABLE", False)
        if url_id:
            update_url_health_failure(url_id, 'нечитаемый')
        else:
            update_competitor_health_failure(competitor_id, 'нечитаемый')
        return {
            'competitor': competitor_name,
            'display_name': display_name,
            'url': url,
            'url_id': url_id,
            'label': label,
            'error_type': 'нечитаемый',
            'is_error': True
        }

    normalized = normalize_content_for_hash(content)
    new_hash = calculate_hash(normalized)

    content_changed = previous_hash and new_hash != previous_hash

    result = None
    llm_summary = ""

    # Получаем предыдущий контент для сравнения (по URL или по конкуренту)
    if url_id:
        previous_content = get_previous_content_for_url(url_id)
    else:
        previous_content = get_previous_content(competitor_id)

    # Дедупликация по content_hash (с учётом URL)
    content_hash = new_hash
    if url_id:
        is_content_duplicate = check_duplicate_change_for_url(competitor_id, content_hash, url_id)
    else:
        is_content_duplicate = check_duplicate_change(competitor_id, content_hash)

    if is_content_duplicate:
        print(f"   ⏭️ Дубликат по контенту: {display_name}")
        result = {
            'competitor': competitor_name,
            'display_name': display_name,
            'url': url,
            'url_id': url_id,
            'label': label,
            'is_error': False,
            'is_duplicate': True
        }
    elif previous_content is None:
        # Первое сканирование — сохраняем контент, но не регистрируем изменения
        print(f"   🆕 Первое сканирование: {display_name}")
        if url_id:
            save_current_content_for_url(url_id, content, content_hash)
        else:
            save_current_content(competitor_id, content, content_hash)
        llm_summary = f"Первое сканирование {display_name}"
        result = {
            'competitor': competitor_name,
            'display_name': display_name,
            'url': url,
            'url_id': url_id,
            'label': label,
            'is_error': False,
            'is_first_scan': True
        }
    else:
        # Есть предыдущий контент — сравниваем через LLM
        print(f"   🔔 Сравнение версий: {display_name}")
        analysis = await analyze_changes_async(competitor_name, content, http_session, previous_content)

        is_meaningful = analysis.get("is_meaningful", False)
        llm_summary = analysis['summary']

        # Сохраняем изменение ТОЛЬКО если оно было обнаружено
        # (даже если не значимо - для аудита)
        # НО на frontend фильтруем по is_meaningful = True
        if url_id:
            save_change_for_url(
                competitor_id=competitor_id,
                category=analysis['category'],
                summary=analysis['summary'],
                tags=analysis['tags'],
                report_id=report_id if is_meaningful else None,
                content_hash=content_hash,
                url_id=url_id,
                scanned_url=url,
                is_meaningful=is_meaningful
            )
        else:
            save_change(
                competitor_id=competitor_id,
                category=analysis['category'],
                summary=analysis['summary'],
                tags=analysis['tags'],
                report_id=report_id if is_meaningful else None,
                content_hash=content_hash,
                is_meaningful=is_meaningful
            )

        # Возвращаем результат только если значимо
        if is_meaningful:
            result = {
                'competitor': competitor_name,
                'display_name': display_name,
                'url': url,
                'url_id': url_id,
                'label': label,
                'category': analysis['category'],
                'summary': analysis['summary'],
                'tags': analysis['tags'],
                'is_error': False,
                'is_meaningful': True
            }
        else:
            result = None
            llm_summary = analysis.get('summary', 'Нет важных изменений')
            print(f"   ⏭️ Нет важных изменений: {display_name}")

        # Обновляем сохранённый контент после анализа
        if url_id:
            save_current_content_for_url(url_id, content, content_hash)
        else:
            save_current_content(competitor_id, content, content_hash)

    scan_id = generate_unique_id("scan_")
    scan_result_id = create_scan_result(
        scan_id, scan_date, competitor_id, new_hash, content_changed,
        content if content_changed else "", llm_summary,
        report_id if content_changed and result and result.get('is_meaningful') else None
    )

    if scan_result_id:
        update_competitor_last_scan(competitor_id, scan_result_id)

    # Успешное сканирование — обновляем health
    if url_id:
        update_url_health_success(url_id)
    else:
        update_competitor_health_success(competitor_id)

    return result

print("✅ Сканирование настроено")

# ============================================================================
# СКАНИРОВАНИЕ TELEGRAM КАНАЛОВ КОНКУРЕНТОВ
# ============================================================================

async def scan_tg_channels_async(
    tg_tasks: List[Tuple[Dict, Dict]],
    report_id: str,
    browser_context,
    http_session: aiohttp.ClientSession
) -> List[Dict[str, Any]]:
    """
    Сканирует Telegram-каналы конкурентов (фаза 2).

    Args:
        tg_tasks: список кортежей (competitor, url_info) для TG-каналов
        report_id: ID отчёта
        browser_context: контекст браузера Playwright
        http_session: HTTP-сессия для LLM-вызовов

    Returns:
        Список результатов с source_type='telegram'
    """
    if not tg_tasks:
        return []

    print(f"\n📱 Фаза 2: Сканирование {len(tg_tasks)} Telegram-каналов конкурентов")
    results = []
    tg_llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_TG)

    for idx, (competitor, url_info) in enumerate(tg_tasks):
        competitor_id = competitor['id']
        competitor_name = competitor.get('name', 'Unknown')
        url_id = url_info.get('id')
        channel_url = url_info.get('url', '')
        last_message_id = url_info.get('last_message_id')

        # Извлекаем username из URL: https://t.me/channel_name -> channel_name
        channel_username = channel_url.rstrip('/').split('/')[-1]
        if not channel_username:
            print(f"  ⚠️ Не удалось извлечь username из {channel_url}")
            continue

        print(f"\n  📡 [{idx+1}/{len(tg_tasks)}] @{channel_username} ({competitor_name})")

        try:
            # 1. Загружаем посты
            min_date = datetime.now(timezone.utc) - timedelta(days=TG_SCAN_PERIOD_DAYS)
            posts = await fetch_tg_channel_posts(
                channel_username, browser_context,
                after_message_id=last_message_id,
                min_date=min_date,
                max_posts=MAX_POSTS_PER_CHANNEL_COMPETITOR
            )

            if not posts:
                print(f"    ℹ️ Нет новых постов")
                continue

            print(f"    📬 Получено {len(posts)} новых постов")

            # 2. Дедупликация по content_hash
            existing_hashes = get_existing_tg_content_hashes(competitor_id)
            new_posts = []
            dupe_posts = []
            for post in posts:
                if post.get('content_hash') and post['content_hash'] in existing_hashes:
                    dupe_posts.append(post)
                else:
                    new_posts.append(post)

            # Обновляем report_id у дублей — чтобы кнопка в боте нашла их по текущему отчёту
            if dupe_posts:
                print(f"    ⏭️ Пропущено дубликатов: {len(dupe_posts)}")
                for post in dupe_posts:
                    try:
                        supabase.table('competitor_tg_posts') \
                            .update({'report_id': report_id}) \
                            .eq('channel_username', channel_username) \
                            .eq('message_id', post['message_id']) \
                            .execute()
                    except Exception as e:
                        print(f"    ⚠️ Ошибка обновления report_id у дубля: {e}")

            if not new_posts:
                # Обновляем last_message_id даже если все дубликаты
                max_msg_id = max(p['message_id'] for p in posts)
                if url_id:
                    update_competitor_url_last_message_id(url_id, max_msg_id)
                continue

            # 3. Сохраняем посты в БД
            saved_posts = []
            for post in new_posts:
                post_id = save_competitor_tg_post(
                    competitor_id, url_id, channel_username, post, report_id
                )
                if post_id:
                    saved_posts.append((post_id, post))

            print(f"    💾 Сохранено {len(saved_posts)} постов")

            # 4. LLM-анализ (конкурентно с семафором)
            async def analyze_and_mark(post_id: int, post: dict):
                async with tg_llm_semaphore:
                    text = post.get('text', '')
                    analysis = await analyze_tg_post_async(competitor_name, text, http_session)

                    title = extract_tg_title(text)
                    summary = analysis.get('summary', '')
                    category = analysis.get('category', CATEGORY_OTHER)
                    tags = analysis.get('tags', [])

                    mark_tg_post_processed(post_id, title, summary, category, tags,
                                           is_meaningful=analysis.get('is_meaningful', False))

                    return {
                        'post_id': post_id,
                        'analysis': analysis,
                        'post': post,
                    }

            llm_tasks = [analyze_and_mark(pid, p) for pid, p in saved_posts]
            llm_results = await asyncio.gather(*llm_tasks, return_exceptions=True)

            # 5. Собираем результаты
            meaningful_count = 0
            for lr in llm_results:
                if isinstance(lr, Exception):
                    print(f"    ⚠️ Ошибка LLM: {lr}")
                    continue

                analysis = lr['analysis']
                post = lr['post']

                if analysis.get('is_meaningful'):
                    meaningful_count += 1
                    results.append({
                        'competitor': competitor_name,
                        'display_name': f"{competitor_name} (@{channel_username})",
                        'url': channel_url,
                        'url_id': url_id,
                        'label': url_info.get('label', 'Telegram'),
                        'category': analysis['category'],
                        'summary': analysis['summary'],
                        'tags': analysis.get('tags', []),
                        'is_error': False,
                        'is_meaningful': True,
                        'source_type': 'telegram',
                        'post_url': post.get('post_url'),
                        'post_date': post.get('post_date'),
                    })

            print(f"    ✅ Важных постов: {meaningful_count}/{len(saved_posts)}")

            # 6. Обновляем last_message_id
            max_msg_id = max(p['message_id'] for p in posts)
            if url_id:
                update_competitor_url_last_message_id(url_id, max_msg_id)

        except Exception as e:
            print(f"    ❌ Ошибка сканирования @{channel_username}: {e}")

        # Задержка между каналами
        if idx < len(tg_tasks) - 1:
            await asyncio.sleep(DELAY_BETWEEN_TG_CHANNELS)

    print(f"\n📱 Telegram-каналы: {len(results)} важных постов найдено")
    return results

print("✅ TG сканирование настроено")

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

async def run_monitoring_async(mode='all'):
    print("🚀 Запуск мониторинга...")
    start_time = time.time()

    init_semaphores()

    current_date = datetime.now().strftime("%Y-%m-%d")
    report_id = generate_unique_id("report_")
    summary_report_id = create_summary_report(report_id, current_date)

    if not summary_report_id:
        send_telegram_message("❌ Ошибка создания отчёта")
        return

    try:
        # Загружаем конкурентов вместе с их URL
        competitors = supabase.table('competitors').select(
            '*, competitor_urls(id, url, label, is_active, sort_order, source_type, last_message_id)'
        ).eq('is_active', True).execute().data
    except Exception as e:
        send_telegram_message(f"❌ Ошибка: {str(e)[:200]}")
        return

    total_competitors = len(competitors)

    # Собираем все URL для сканирования
    scan_tasks_list = []
    for competitor in competitors:
        urls = competitor.get('competitor_urls', [])

        if urls:
            # Сортируем по sort_order и фильтруем активные
            active_urls = [u for u in urls if u.get('is_active', True)]
            active_urls.sort(key=lambda x: x.get('sort_order', 0))

            for url_info in active_urls:
                scan_tasks_list.append((competitor, url_info))
        else:
            # Fallback на старое поле url если новых URL нет
            if competitor.get('url'):
                fallback_url_info = {
                    'id': None,
                    'url': competitor['url'],
                    'label': 'Главная',
                    'is_active': True
                }
                scan_tasks_list.append((competitor, fallback_url_info))

    # Разделяем на веб-сайты и Telegram-каналы
    website_tasks = [(c, u) for c, u in scan_tasks_list if u.get('source_type', 'website') == 'website']
    tg_tasks = [(c, u) for c, u in scan_tasks_list if u.get('source_type') == 'telegram']

    total_urls = len(website_tasks)
    total_tg_channels = len(tg_tasks)
    print(f"🌐 Конкурентов: {total_competitors}, URL: {total_urls}, TG-каналов: {total_tg_channels}")

    categorized_changes = {
        CATEGORY_PRODUCTS: [],
        CATEGORY_PRICES: [],
        CATEGORY_NEWS: [],
        CATEGORY_TECHNICAL: [],
        CATEGORY_SERVICES: [],
        CATEGORY_PROMOTION: [],
        CATEGORY_OTHER: [],
    }
    failed_sites = []
    duplicates_count = 0
    first_scans_count = 0

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, ssl=False)

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

            # Фаза 1: Batch-обработка веб-сайтов
            results = []
            if mode in ('all', 'websites'):
                total_batches = (len(website_tasks) + BATCH_SIZE - 1) // BATCH_SIZE

                for batch_idx in range(total_batches):
                    start_idx = batch_idx * BATCH_SIZE
                    end_idx = min(start_idx + BATCH_SIZE, len(website_tasks))
                    batch = website_tasks[start_idx:end_idx]

                    tasks = [
                        scan_url_async(comp, url_info, summary_report_id, current_date, http_session, browser_context)
                        for comp, url_info in batch
                    ]
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    results.extend(batch_results)

                    processed = end_idx
                    print(f"📦 Батч {batch_idx + 1}/{total_batches}: обработано {processed}/{total_urls}")

                    # Пауза между батчами (кроме последнего)
                    if batch_idx < total_batches - 1:
                        await asyncio.sleep(BATCH_DELAY)

            # Фаза 2: Сканирование Telegram-каналов конкурентов
            tg_results = []
            if mode in ('all', 'telegram'):
                tg_results = await scan_tg_channels_async(
                    tg_tasks, summary_report_id, browser_context, http_session
                )

            await browser_context.close()
            await browser.close()

    for result in results:
        if isinstance(result, Exception) or not result:
            continue

        if result.get('is_error'):
            failed_sites.append(result)
        elif result.get('is_duplicate'):
            duplicates_count += 1
        elif result.get('is_first_scan'):
            first_scans_count += 1
        elif result.get('is_meaningful', True):  # Только информативные изменения
            category = result.get('category', CATEGORY_TECHNICAL)
            if category in categorized_changes:
                categorized_changes[category].append(result)

    # Добавляем результаты Telegram-каналов
    tg_meaningful_count = 0
    for tg_result in tg_results:
        if tg_result.get('is_meaningful'):
            tg_meaningful_count += 1
            category = tg_result.get('category', CATEGORY_TECHNICAL)
            if category in categorized_changes:
                categorized_changes[category].append(tg_result)

    elapsed = int(time.time() - start_time)
    print(f"⏱️ Время: {elapsed} сек")

    total_changes = sum(len(v) for k, v in categorized_changes.items() if k not in (CATEGORY_TECHNICAL, CATEGORY_OTHER))
    total_ok = total_urls - len(failed_sites)

    # === СОХРАНЯЕМ СТАТИСТИКУ В БД ===
    update_summary_report_with_stats(
        summary_report_id,
        total_sites=total_urls,
        successful_sites=total_ok,
        changes_count=total_changes,
        problems_count=len(failed_sites),
        duration_seconds=elapsed
    )

    pdf_path = generate_pdf_report(current_date, total_competitors, total_urls, categorized_changes, failed_sites, duplicates_count, first_scans_count, tg_meaningful_count)

    errors_by_type = {}
    for site in failed_sites:
        error_type = site.get('error_type', 'другое')
        errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1

    error_stats_lines = []
    error_labels = {
        "таймаут": "⏱️ Таймаут",
        "нет_соединения": "🔌 Нет соединения",
        "cloudflare": "🛡️ Cloudflare",
        "доступ_запрещён": "🚫 Запрещён",
        "не_найден": "❓ Не найден",
        "ошибка_сервера": "💥 Сервер",
        "нечитаемый": "📄 Нечитаемый",
        "мало_контента": "📄 Мало контента",
    }

    sorted_errors = sorted(errors_by_type.items(), key=lambda x: -x[1])
    for error_type, count in sorted_errors:
        label = error_labels.get(error_type, error_type)
        error_stats_lines.append(f"   {label}: {count}")

    error_stats_text = "\n".join(error_stats_lines) if error_stats_lines else "   Нет данных"

    success_rate = round(total_ok / total_urls * 100, 1) if total_urls > 0 else 0

    keyboard = None
    if tg_meaningful_count > 0:
        keyboard = {
            "inline_keyboard": [[
                {"text": f"📱 Читать TG-посты ({tg_meaningful_count}) — по одному",
                 "callback_data": f"show_tg_posts:{summary_report_id}:0"}
            ]]
        }

    if mode == 'telegram':
        msg = f"""📱 <b>Мониторинг TG-каналов конкурентов завершён</b>

📅 Дата: {current_date}
⏱️ Время: {elapsed} сек
📱 Каналов проверено: <b>{total_tg_channels}</b>

✅ <b>Важных постов: {tg_meaningful_count}</b>
   🏷️ Продукты: {len(categorized_changes[CATEGORY_PRODUCTS])}
   💰 Цены/акции: {len(categorized_changes[CATEGORY_PRICES])}
   🛠️ Сервис: {len(categorized_changes[CATEGORY_SERVICES])}
   📰 Новости: {len(categorized_changes[CATEGORY_NEWS])}
   📣 Продвижение: {len(categorized_changes[CATEGORY_PROMOTION])}"""
        if tg_meaningful_count > 0:
            msg += "\n\n📎 Сводка во вложении · подробно с фильтрами — в мини-приложении (кнопка ниже)"
            wake_up_bot()
        if tg_meaningful_count == 0:
            send_telegram_message(msg, reply_markup=keyboard)
        else:
            send_telegram_document(pdf_path, msg, reply_markup=keyboard)
        try:
            os.remove(pdf_path)
        except:
            pass
        print("✅ Готово!")
        return
    else:
        tg_line = f"\n📱 TG-каналов: <b>{total_tg_channels}</b> (важных постов: {tg_meaningful_count})" if total_tg_channels > 0 else ""

        msg = f"""📊 <b>Мониторинг завершён</b>

📅 Дата: {current_date}
⏱️ Время: {elapsed} сек
🌐 Конкурентов: <b>{total_competitors}</b>
🔗 URL проверено: <b>{total_urls}</b>{tg_line}

✅ <b>Успешно: {total_ok}</b> ({success_rate}%)

🔄 <b>Важные изменения: {total_changes}</b>
   🏷️ Продукты: {len(categorized_changes[CATEGORY_PRODUCTS])}
   💰 Цены/акции: {len(categorized_changes[CATEGORY_PRICES])}
   📰 Новости: {len(categorized_changes[CATEGORY_NEWS])}
   📣 Продвижение: {len(categorized_changes[CATEGORY_PROMOTION])}

🔁 <b>Пропущено дубликатов: {duplicates_count}</b>
🆕 <b>Первых сканирований: {first_scans_count}</b>

⚠️ <b>Неуспешно: {len(failed_sites)}</b>
{error_stats_text}

📎 Сводка во вложении · подробно с фильтрами — в мини-приложении (кнопка ниже)"""
        if tg_meaningful_count > 0:
            wake_up_bot()

    send_telegram_document(pdf_path, msg, reply_markup=keyboard)
    
    try:
        os.remove(pdf_path)
    except:
        pass

    print("✅ Готово!")


def run_monitoring_system(mode='all'):
    asyncio.run(run_monitoring_async(mode))

print("✅ Система готова")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['all', 'websites', 'telegram'], default='all')
    parser.add_argument('--test', action='store_true', help='Тестовый режим: уведомления только администратору')
    args = parser.parse_args()
    if args.test:
        TEST_MODE = True
    run_monitoring_system(args.mode)
