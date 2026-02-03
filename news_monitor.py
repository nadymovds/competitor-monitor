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

# === ВЕБ-СКАНИРОВАНИЕ ===
WEB_PLAYWRIGHT_TIMEOUT = 45000
WEB_REQUEST_TIMEOUT = 45
MAX_NEWS_PER_WEBSITE = 20
DELAY_BETWEEN_WEBSITES = 3

DEFAULT_CSS_CONFIG = {
    "item": "article, .news-item, .post, .news, .entry",
    "title": "h1, h2, h3, .title, .headline",
    "text": "p, .content, .excerpt, .summary, .description",
    "date": "time, .date, [datetime], .published, .timestamp",
    "link": "a[href]"
}

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
    'Дорожные условия': '☁',
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


def clean_text_for_pdf(text: str) -> str:
    """Удаляет эмодзи и невидимые символы, не поддерживаемые шрифтом DejaVuSans в PDF."""
    if not text:
        return ""
    result = []
    for char in text:
        cp = ord(char)  
        # Пропускаем символы за пределами BMP (эмодзи U+1F000+ и т.д.)
        if cp > 0xFFFF:
            continue
        # Пропускаем вариационные селекторы (переключают символ в emoji-стиль)
        if 0xFE00 <= cp <= 0xFE0F:
            continue
        # Пропускаем zero-width и bidi-символы
        if cp in (0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0xFEFF):
            continue
        if 0x202A <= cp <= 0x202E:
            continue
        # Заменяем проблемные символы, которые не отображаются в DejaVuSans
        # но оставляем все стандартные латинские, кириллические и распространенные символы
        if cp < 32 and cp not in (9, 10, 13):  # Управляющие символы кроме tab, LF, CR
            continue
        result.append(char)
    text = ''.join(result)
    # Убираем лишние пробелы после удаления символов
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)  # Не более 2 переносов подряд
    # Экранируем спецсимволы XML для ReportLab Paragraph
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text.strip()


def clean_html_content_for_web(soup: BeautifulSoup) -> str:
    """Очистка HTML от служебных элементов для веб-сайтов."""
    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'iframe', 'aside']):
        element.decompose()
    text = soup.get_text(separator=' ', strip=True)
    return ' '.join(text.split())


def is_protection_page(content: str) -> bool:
    """Детекция страниц защиты от ботов (Cloudflare, CAPTCHA и др.)."""
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


# === ПАРСИНГ ДАТ ИЗ ТЕКСТА ===
MONTHS_RU = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
    'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
    'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4,
    'май': 5, 'июн': 6, 'июл': 7, 'авг': 8,
    'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12,
}


def parse_date_from_text(date_str: str) -> datetime | None:
    """Парсинг дат из текста: '01.02.2025', '15 января 2025', 'вчера', ISO-формат."""
    if not date_str:
        return None

    date_str = date_str.strip().lower()
    now = datetime.now()

    # Относительные даты
    if 'сегодня' in date_str:
        return now.replace(hour=12, minute=0, second=0, microsecond=0)
    if 'вчера' in date_str:
        return (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)

    # ISO-формат: 2025-01-15T10:30:00
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        pass

    # Формат DD.MM.YYYY или DD/MM/YYYY
    match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', date_str)
    if match:
        try:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return datetime(year, month, day, 12, 0, 0)
        except ValueError:
            pass

    # Формат YYYY-MM-DD
    match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
    if match:
        try:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return datetime(year, month, day, 12, 0, 0)
        except ValueError:
            pass

    # Русский формат: "15 января 2025" или "15 янв 2025"
    for month_name, month_num in MONTHS_RU.items():
        if month_name in date_str:
            match = re.search(rf'(\d{{1,2}})\s*{month_name}[а-я]*\s*(\d{{4}})?', date_str)
            if match:
                try:
                    day = int(match.group(1))
                    year = int(match.group(2)) if match.group(2) else now.year
                    return datetime(year, month_num, day, 12, 0, 0)
                except ValueError:
                    pass
            break

    return None


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
# ПАРСИНГ ВЕБ-САЙТОВ
# ============================================================================

async def fetch_website_news_page(url: str, browser_context) -> str:
    """Загрузка HTML страницы веб-сайта через Playwright со stealth-режимом."""
    async with browser_semaphore:
        page = await browser_context.new_page()
        try:
            # Stealth-настройки
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

            # Случайная задержка
            await asyncio.sleep(random.uniform(0.2, 0.5))

            # Загрузка страницы с разными стратегиями
            load_success = False
            for wait_strategy in ['domcontentloaded', 'load', 'networkidle']:
                try:
                    await page.goto(url, timeout=WEB_PLAYWRIGHT_TIMEOUT, wait_until=wait_strategy)
                    load_success = True
                    break
                except Exception as e:
                    if 'timeout' not in str(e).lower():
                        break
                    continue

            if not load_success:
                await page.close()
                return ""

            # Ждём загрузки динамического контента
            await page.wait_for_timeout(2500)

            # Скролл для активации lazy-load
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
                await page.wait_for_timeout(500)
            except:
                pass

            html = await page.content()

            # Проверка на страницу защиты
            if is_protection_page(html):
                print(f"  ⚠️ Обнаружена защита от ботов на {url}")
                await page.close()
                return ""

            return html

        except PlaywrightTimeout:
            print(f"  ⚠️ Таймаут при загрузке {url}")
            return ""
        except Exception as e:
            print(f"  ❌ Ошибка загрузки {url}: {e}")
            return ""
        finally:
            try:
                await page.close()
            except:
                pass


def parse_news_items_from_html(html: str, base_url: str, css_config: dict = None) -> list:
    """Парсинг новостей из HTML по CSS-селекторам.

    Возвращает список: [{title, text, date, article_url, content_hash}, ...]
    """
    if not html:
        return []

    config = css_config or DEFAULT_CSS_CONFIG
    soup = BeautifulSoup(html, 'lxml')
    news_items = []

    # Поиск элементов новостей
    item_selectors = [s.strip() for s in config.get('item', '').split(',')]
    items = []
    for selector in item_selectors:
        if selector:
            items.extend(soup.select(selector))

    if not items:
        print(f"  ⚠️ Не найдены элементы новостей по селекторам: {config.get('item')}")
        return []

    from urllib.parse import urljoin

    for item in items[:MAX_NEWS_PER_WEBSITE]:
        try:
            # Извлечение заголовка
            title = ""
            title_selectors = [s.strip() for s in config.get('title', '').split(',')]
            for selector in title_selectors:
                if selector:
                    title_elem = item.select_one(selector)
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        break

            # Извлечение текста
            text = ""
            text_selectors = [s.strip() for s in config.get('text', '').split(',')]
            for selector in text_selectors:
                if selector:
                    text_elems = item.select(selector)
                    if text_elems:
                        text = ' '.join(elem.get_text(strip=True) for elem in text_elems)
                        break

            # Если заголовок и текст пустые — пропускаем
            if not title and not text:
                continue

            # Извлечение даты
            post_date = None
            date_selectors = [s.strip() for s in config.get('date', '').split(',')]
            for selector in date_selectors:
                if selector:
                    date_elem = item.select_one(selector)
                    if date_elem:
                        # Пробуем datetime атрибут
                        datetime_attr = date_elem.get('datetime')
                        if datetime_attr:
                            post_date = parse_date_from_text(datetime_attr)
                        if not post_date:
                            post_date = parse_date_from_text(date_elem.get_text(strip=True))
                        if post_date:
                            break

            # Извлечение ссылки на статью
            article_url = ""
            link_selectors = [s.strip() for s in config.get('link', '').split(',')]
            for selector in link_selectors:
                if selector:
                    link_elem = item.select_one(selector)
                    if link_elem and link_elem.get('href'):
                        href = link_elem.get('href')
                        article_url = urljoin(base_url, href)
                        break

            # Формируем контент для хеширования
            content_for_hash = f"{title}\n{text}".strip()
            if not content_for_hash:
                continue

            news_items.append({
                'title': title[:500] if title else "",
                'text': text[:5000] if text else "",
                'post_date': post_date,
                'article_url': article_url,
                'content_hash': calculate_hash(content_for_hash),
            })

        except Exception as e:
            print(f"  ⚠️ Ошибка парсинга элемента новости: {e}")
            continue

    return news_items


async def scan_website_source(source: dict, browser_context, existing_hashes: set) -> list:
    """Сканирование одного веб-источника новостей.

    Возвращает список новых постов для сохранения.
    """
    url = source.get('url')
    title = source.get('title') or source.get('username') or url
    css_config = source.get('css_config') or DEFAULT_CSS_CONFIG

    print(f"  🌐 Загрузка {url}...")

    html = await fetch_website_news_page(url, browser_context)
    if not html:
        return []

    news_items = parse_news_items_from_html(html, url, css_config)
    print(f"  📰 Найдено элементов: {len(news_items)}")

    # Фильтрация дубликатов по content_hash
    new_items = []
    for item in news_items:
        content_hash = item.get('content_hash')
        if content_hash and content_hash not in existing_hashes:
            new_items.append(item)
            existing_hashes.add(content_hash)

    return new_items


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

def save_post(channel_id: int, post_data: dict, source_type: str = 'telegram') -> int | None:
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
            'source_type': source_type,
        }
        result = supabase.table('news_posts').upsert(data, on_conflict='channel_id,message_id').execute()
        if result.data:
            return result.data[0].get('id')
        return None
    except Exception as e:
        print(f"  ⚠️ Ошибка сохранения поста {post_data.get('message_id')}: {e}")
        return None


def save_web_post(channel_id: int, post_data: dict) -> int | None:
    """Сохранение веб-новости в news_posts. Возвращает id записи.

    Для веб-новостей нет message_id, используем content_hash для дедупликации.
    """
    try:
        content_hash = post_data.get('content_hash')
        if not content_hash:
            return None

        # Проверяем существование по content_hash
        existing = (supabase.table('news_posts')
                    .select('id')
                    .eq('channel_id', channel_id)
                    .eq('content_hash', content_hash)
                    .execute())
        if existing.data:
            return existing.data[0].get('id')

        # Генерируем уникальный message_id на основе хеша
        message_id = int(content_hash[:8], 16) % 2147483647

        data = {
            'channel_id': channel_id,
            'message_id': message_id,
            'post_url': post_data.get('article_url', ''),
            'title': post_data.get('title', ''),
            'content_text': post_data.get('text', ''),
            'post_date': post_data['post_date'].isoformat() if post_data.get('post_date') else None,
            'has_photo': False,
            'has_video': False,
            'has_document': False,
            'views_count': 0,
            'content_hash': content_hash,
            'source_type': 'website',
            'article_url': post_data.get('article_url', ''),
        }
        result = supabase.table('news_posts').insert(data).execute()
        if result.data:
            return result.data[0].get('id')
        return None
    except Exception as e:
        print(f"  ⚠️ Ошибка сохранения веб-новости: {e}")
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

def get_processed_content_hashes(period_start: datetime) -> set:
    """Выборка content_hash уже обработанных постов за период (для дедупликации)."""
    try:
        result = (supabase.table('news_posts')
                  .select('content_hash')
                  .eq('is_processed', True)
                  .gte('post_date', period_start.isoformat())
                  .execute())
        return {r['content_hash'] for r in (result.data or []) if r.get('content_hash')}
    except Exception as e:
        print(f"⚠️ Ошибка получения хешей обработанных постов: {e}")
        return set()

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

ДОСТУПНЫЕ КАТЕГОРИИ (ID: название — описание):
{categories_desc}

ПРАВИЛА:
- Внимательно читай ОПИСАНИЕ каждой категории — оно определяет, какие темы к ней относятся
- Выбери от 1 до 3 наиболее подходящих категорий
- Для каждой категории укажи уверенность от 0.0 до 1.0
- ВСЕГДА назначай хотя бы одну категорию. Если пост не подходит ни к одной специализированной категории, назначь категорию "Прочее"
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

        # Фоллбек: если категории не назначены — назначаем "Прочее"
        if not post_categories:
            other_cat = next((c for c in categories if c['name'] == 'Прочее'), None)
            if other_cat:
                post_categories = [{'category_id': other_cat['id'], 'confidence': 0.5}]
                print(f"  ℹ️ Пост {post_id}: категории не определены, назначена «Прочее»")

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
                              posts: list, channels_count: int) -> str:
    """Генерация PDF-дайджеста новостей, отсортированных по дате публикации.

    posts: плоский список постов с полем category_tags.
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
        'post_title': ParagraphStyle('PostTitle', fontName=font_bold, fontSize=10, spaceBefore=10,
                                     spaceAfter=2),
        'summary': ParagraphStyle('Summary', fontName=font_regular, fontSize=9, spaceAfter=2,
                                  leading=12, leftIndent=10),
        'meta': ParagraphStyle('Meta', fontName=font_regular, fontSize=8, spaceAfter=2,
                               leftIndent=10, textColor=colors.HexColor('#666666')),
        'tags': ParagraphStyle('Tags', fontName=font_regular, fontSize=8, spaceAfter=2,
                               leftIndent=10, textColor=colors.HexColor('#555555')),
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

    # Очистка текста постов для PDF (удаление эмодзи, обработка пустых заголовков)
    cleaned_posts = []
    for post in posts:
        p_title = clean_text_for_pdf(post.get('title', ''))
        p_summary = clean_text_for_pdf(post.get('summary', ''))
        p_content = clean_text_for_pdf(post.get('content_text', ''))
        
        # Обеспечиваем наличие заголовка любой ценой
        if not p_title or len(p_title.strip()) < 5:
            if p_summary:
                # Используем summary как заголовок
                p_title = p_summary[:150] + ('...' if len(p_summary) > 150 else '')
                p_summary = ''  # Не дублировать summary
            elif p_content:
                # Берем первую непустую строку длиной >= 5 символов из контента
                for line in p_content.split('\n'):
                    line = line.strip()
                    if len(line) >= 5:
                        p_title = line[:150] + ('...' if len(line) > 150 else '')
                        break
                if not p_title or len(p_title.strip()) < 5:
                    p_title = p_content[:150].replace('\n', ' ') + ('...' if len(p_content) > 150 else '')
            else:
                # Последний fallback: используем название канала
                channel_title = post.get('channel_title', 'Источник')
                p_title = f"Новость от {channel_title}"

        # Обеспечиваем наличие summary: берём из LLM-summary, либо из контента
        if not p_summary and p_content:
            # Извлекаем preview из контента
            content_lines = [l.strip() for l in p_content.split('\n') if l.strip()]
            # Пропускаем первую строку если она совпадает с заголовком
            start_idx = 0
            if content_lines and p_title and content_lines[0].startswith(p_title[:30]):
                start_idx = 1
            rest_lines = content_lines[start_idx:]
            if rest_lines:
                rest = '\n'.join(rest_lines)
                p_summary = rest[:500] + ('...' if len(rest) > 500 else '')
            elif len(p_content) > len(p_title) + 20:
                p_summary = p_content[:500] + ('...' if len(p_content) > 500 else '')
        
        cleaned_posts.append({**post, 'title': p_title, 'summary': p_summary})

    # Статистика
    total_posts = len(cleaned_posts)
    stats = f"Источников: {channels_count} | Новостей: {total_posts}"
    content.append(Paragraph(stats, styles['subtitle']))
    content.append(Spacer(1, 10))

    for post_number, post in enumerate(cleaned_posts, start=1):
        title = post['title']
        summary = post['summary']
        post_url = post.get('post_url', '')
        channel_title = clean_text_for_pdf(post.get('channel_title', ''))
        post_date = post.get('post_date', '')
        views = post.get('views_count', 0)
        category_tags = post.get('category_tags', [])
        source_type = post.get('source_type', 'telegram')

        # Иконка типа источника (ASCII-символы для совместимости с PDF-шрифтом)
        source_icon = "[TG]" if source_type == 'telegram' else "[Web]"

        # Заголовок поста с номером и иконкой источника (кликабельный если есть URL)
        if post_url:
            title_text = f"{post_number}. {source_icon} <a href='{post_url}' color='#1a1a1a'><b>{title}</b></a>"
        else:
            title_text = f"{post_number}. {source_icon} <b>{title}</b>"
        content.append(Paragraph(title_text, styles['post_title']))

        # Краткое содержание
        if summary:
            content.append(Paragraph(summary, styles['summary']))

        # Теги категорий
        if category_tags:
            tag_spans = []
            for tag in category_tags:
                tag_name = tag.get('name', '')
                tag_color = tag.get('color', '#2c5aa0')
                icon = CATEGORY_ICONS.get(tag_name, DEFAULT_CATEGORY_ICON)
                tag_spans.append(f"<font color='{tag_color}'>{icon} {tag_name}</font>")
            content.append(Paragraph(" &nbsp; ".join(tag_spans), styles['tags']))

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
    """Главная функция: сканирование каналов и веб-сайтов → LLM-обработка → PDF-дайджест → Telegram."""
    print("🚀 Запуск мониторинга новостей...")
    start_time = time.time()

    # 1. Инициализация семафоров
    init_semaphores()

    # 2. Уведомление о старте
    send_telegram_message("🚀 <b>Запуск мониторинга новостей</b>\n📰 Сканирование источников...")

    # 3. Загрузка источников из БД
    all_sources = get_active_channels()
    if not all_sources:
        send_telegram_message("❌ Нет активных источников для мониторинга")
        print("❌ Нет активных источников")
        return

    # 3.1 Разделение на TG-каналы и веб-сайты
    tg_channels = [s for s in all_sources if s.get('source_type', 'telegram') == 'telegram']
    web_sources = [s for s in all_sources if s.get('source_type') == 'website']

    print(f"📋 Загружено источников: {len(all_sources)} (📱 TG: {len(tg_channels)}, 🌐 Web: {len(web_sources)})")

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

    # Счётчики
    total_new_posts = 0
    tg_channels_scanned = 0
    tg_channels_with_errors = 0
    web_sources_scanned = 0
    web_sources_with_errors = 0
    total_web_posts = 0
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

            # === ФАЗА 1A: СКАНИРОВАНИЕ TG КАНАЛОВ ===
            if tg_channels:
                print("\n" + "=" * 60)
                print("ФАЗА 1A: СКАНИРОВАНИЕ TG КАНАЛОВ")
                print("=" * 60)

                for i, channel in enumerate(tg_channels, start=1):
                    channel_id = channel['id']
                    username = channel['username']
                    last_message_id = channel.get('last_message_id')

                    print(f"\n📱 [{i}/{len(tg_channels)}] Сканирование @{username} (last_id: {last_message_id})...")

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
                                post_id = save_post(channel_id, post_data, source_type='telegram')
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

                        tg_channels_scanned += 1
                    except Exception as e:
                        print(f"  ❌ Ошибка сканирования @{username}: {e}")
                        tg_channels_with_errors += 1

                    # Пауза между каналами
                    if i < len(tg_channels):
                        await asyncio.sleep(DELAY_BETWEEN_CHANNELS)

                print(f"\n📊 Фаза 1A завершена: {tg_channels_scanned} каналов, {total_new_posts} новых постов, {tg_channels_with_errors} ошибок")

            # === ФАЗА 1B: СКАНИРОВАНИЕ ВЕБ-САЙТОВ ===
            if web_sources:
                print("\n" + "=" * 60)
                print("ФАЗА 1B: СКАНИРОВАНИЕ ВЕБ-САЙТОВ")
                print("=" * 60)

                # Получаем существующие хеши для дедупликации
                existing_hashes = get_processed_content_hashes(period_start)

                for i, source in enumerate(web_sources, start=1):
                    source_id = source['id']
                    source_url = source.get('url', '')
                    source_title = source.get('title') or source_url

                    print(f"\n🌐 [{i}/{len(web_sources)}] Сканирование {source_title}...")

                    try:
                        new_items = await scan_website_source(source, browser_context, existing_hashes)

                        if new_items:
                            saved_count = 0
                            for item in new_items:
                                post_id = save_web_post(source_id, item)
                                if post_id:
                                    saved_count += 1

                            total_web_posts += saved_count
                            print(f"  ✅ Найдено {len(new_items)} новостей, сохранено {saved_count}")
                        else:
                            print(f"  ℹ️ Новых новостей нет")

                        web_sources_scanned += 1
                    except Exception as e:
                        print(f"  ❌ Ошибка сканирования {source_title}: {e}")
                        web_sources_with_errors += 1

                    # Пауза между сайтами
                    if i < len(web_sources):
                        await asyncio.sleep(DELAY_BETWEEN_WEBSITES)

                print(f"\n📊 Фаза 1B завершена: {web_sources_scanned} сайтов, {total_web_posts} новых новостей, {web_sources_with_errors} ошибок")

            # 8. Закрытие браузера
            await browser_context.close()
            await browser.close()

        # Общая статистика по фазе 1
        total_sources_scanned = tg_channels_scanned + web_sources_scanned
        total_all_posts = total_new_posts + total_web_posts
        total_errors = tg_channels_with_errors + web_sources_with_errors
        print(f"\n📊 Фаза 1 завершена: {total_sources_scanned} источников, {total_all_posts} новых записей, {total_errors} ошибок")

        # === ФАЗА 2: LLM-ОБРАБОТКА ===
        print("\n" + "=" * 60)
        print("ФАЗА 2: LLM-ОБРАБОТКА")
        print("=" * 60)

        # 9. Получение необработанных постов
        unprocessed = get_unprocessed_posts(period_start)
        print(f"📝 Необработанных постов: {len(unprocessed)}")

        if unprocessed:
            # 9.1 Дедупликация по content_hash — пропуск постов с уже обработанным контентом
            processed_hashes = get_processed_content_hashes(period_start)
            unique_posts = []
            skipped_duplicates = 0
            seen_hashes = set()

            for post in unprocessed:
                h = post.get('content_hash')
                if h:
                    if h in processed_hashes or h in seen_hashes:
                        mark_post_processed(post['id'], extract_title(post.get('content_text', '')), '')
                        skipped_duplicates += 1
                        continue
                    seen_hashes.add(h)
                unique_posts.append(post)

            if skipped_duplicates > 0:
                print(f"⏭️ Пропущено дубликатов по content_hash: {skipped_duplicates}")

            # 10. Параллельная обработка через asyncio.gather + llm_semaphore
            tasks = [
                process_post_with_llm(post, categories, http_session)
                for post in unique_posts
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
            # Плоский список постов с тегами категорий (без группировки)
            posts_flat = []
            seen_urls = set()

            for post in digest_posts:
                post_url = post.get('post_url', '')
                if post_url in seen_urls:
                    continue
                seen_urls.add(post_url)

                # Собираем категории поста как теги
                post_categories = post.get('news_post_categories', [])
                category_tags = []
                for pc in post_categories:
                    cat_info_raw = pc.get('news_categories', {})
                    if not cat_info_raw or not cat_info_raw.get('is_visible', True):
                        continue
                    category_tags.append({
                        'name': cat_info_raw['name'],
                        'color': cat_info_raw.get('color', '#2c5aa0'),
                    })

                if not category_tags:
                    continue

                channel_info = post.get('news_channels', {})
                source_type = post.get('source_type', 'telegram')
                posts_flat.append({
                    'title': post.get('title', ''),
                    'summary': post.get('summary', ''),
                    'content_text': post.get('content_text', ''),
                    'post_url': post_url,
                    'channel_title': channel_info.get('title') or channel_info.get('username', ''),
                    'post_date': post.get('post_date', ''),
                    'views_count': post.get('views_count', 0),
                    'category_tags': category_tags,
                    'source_type': source_type,
                })

            # Сортировка по дате (свежие первыми)
            def parse_date_for_sort(d):
                if not d:
                    return datetime.min
                if isinstance(d, str):
                    try:
                        return datetime.fromisoformat(d.replace('Z', '+00:00'))
                    except ValueError:
                        return datetime.min
                return d
            posts_flat.sort(key=lambda p: parse_date_for_sort(p['post_date']), reverse=True)

            # 12. Генерация PDF
            pdf_path = generate_news_digest_pdf(
                digest_date=current_date,
                period_start=period_start,
                period_end=period_end,
                posts=posts_flat,
                channels_count=len(all_sources),
            )

            # 13. Сохранение дайджеста в БД
            all_post_ids = [p.get('id') for p in digest_posts if p.get('id')]
            total_digest_posts = len(posts_flat)

            digest_data = {
                'digest_date': current_date,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'total_posts': total_digest_posts,
                'total_channels': len(all_sources),
            }
            digest_id = save_digest(digest_data, all_post_ids)

    # Итоговая статистика
    elapsed = int(time.time() - start_time)
    print(f"\n⏱️ Время выполнения: {elapsed} сек")

    # 14. Отправка PDF + сводного сообщения в Telegram
    total_digest = len(digest_posts) if digest_posts else 0
    total_all_new = total_new_posts + total_web_posts

    summary_msg = f"""📊 <b>Мониторинг новостей завершён</b>

📅 Период: {period_start.strftime('%d.%m.%Y')} — {period_end.strftime('%d.%m.%Y')}
⏱️ Время: {elapsed} сек

📱 TG-каналов: <b>{tg_channels_scanned}</b> из {len(tg_channels)}
🌐 Веб-сайтов: <b>{web_sources_scanned}</b> из {len(web_sources)}
📝 Новых записей: <b>{total_all_new}</b> (📱 {total_new_posts} + 🌐 {total_web_posts})
🤖 Обработано LLM: <b>{processed_count}</b>
📰 Постов в дайджесте: <b>{total_digest}</b>"""

    if tg_channels_with_errors or web_sources_with_errors:
        summary_msg += f"\n⚠️ Ошибки: 📱 {tg_channels_with_errors}, 🌐 {web_sources_with_errors}"

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
