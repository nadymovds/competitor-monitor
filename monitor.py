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
from datetime import datetime
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
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

LLM_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# === ТАЙМАУТЫ И RETRY ===
REQUEST_TIMEOUT = 45
PLAYWRIGHT_TIMEOUT = 45000  # 45 секунд для Playwright
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]

MIN_CONTENT_LENGTH = 200

# === СТРАТЕГИЯ ЗАГРУЗКИ ===
# Playwright как основной метод для максимальной совместимости
USE_PLAYWRIGHT_FIRST = True  # Новая опция!

# === РОТАЦИЯ USER-AGENT ===
USER_AGENTS = [
    # Chrome Windows (самый популярный)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

USER_AGENT = USER_AGENTS[0]

MAX_CONCURRENT_REQUESTS = 15
MAX_CONCURRENT_BROWSER = 8  # Увеличено — основная нагрузка на браузер
MAX_CONCURRENT_LLM = 5

# Задержка между запросами (анти-детект)
MIN_REQUEST_DELAY = 0.5  # секунд
MAX_REQUEST_DELAY = 2.0  # секунд

CATEGORY_PRODUCTS = "products"
CATEGORY_PRICES = "prices"
CATEGORY_NEWS = "news"
CATEGORY_TECHNICAL = "technical"

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

def send_telegram_message(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=30)
        return True
    except:
        return False

def send_telegram_document(file_path: str, caption: str = "") -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}, 
                         files={'document': f}, timeout=60)
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

async def random_delay():
    """Случайная задержка между запросами для имитации человека"""
    delay = random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY)
    await asyncio.sleep(delay)

print("✅ Утилиты загружены")

# ============================================================================
# ЗАГРУЗКА КОНТЕНТА — УЛУЧШЕННАЯ ВЕРСИЯ
# ============================================================================

def get_headers_for_url(url: str, attempt: int = 0) -> dict:
    """Генерирует заголовки с ротацией User-Agent и Referer"""
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
    """Асинхронная загрузка через aiohttp (быстрый метод для простых сайтов)"""
    
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
    Рендеринг через Playwright с stealth-техниками и retry логикой.
    Это основной метод для надёжного получения контента.
    """
    try:
        async with browser_semaphore:
            page = await browser_context.new_page()
            
            try:
                # === STEALTH НАСТРОЙКИ ===
                # Удаляем признаки автоматизации
                await page.add_init_script("""
                    // Удаляем webdriver флаг
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Подменяем plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Подменяем languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ru-RU', 'ru', 'en-US', 'en']
                    });
                    
                    // Chrome runtime
                    window.chrome = {
                        runtime: {}
                    };
                    
                    // Permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)
                
                # Блокируем тяжёлые ресурсы для ускорения
                await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,mp4,webm,mp3,wav,avi}", 
                               lambda route: route.abort())
                
                # Также блокируем аналитику и рекламу
                await page.route("**/*google-analytics*", lambda route: route.abort())
                await page.route("**/*googletagmanager*", lambda route: route.abort())
                await page.route("**/*facebook*", lambda route: route.abort())
                await page.route("**/*yandex*metrika*", lambda route: route.abort())
                
                # Случайная задержка перед запросом
                await asyncio.sleep(random.uniform(0.3, 1.0))
                
                # Пробуем загрузить страницу
                load_error = None
                for wait_strategy in ['domcontentloaded', 'load', 'networkidle']:
                    try:
                        await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until=wait_strategy)
                        load_error = None
                        break
                    except Exception as e:
                        load_error = str(e)
                        if 'timeout' in str(e).lower():
                            continue
                        break
                
                if load_error and 'timeout' in load_error.lower():
                    await page.close()
                    return (None, "таймаут")
                
                # Ждём загрузку динамического контента
                await page.wait_for_timeout(2000)
                
                # Пробуем прокрутить страницу (активирует lazy-load)
                try:
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
    
    Стратегия:
    1. Сначала пробуем Playwright (надёжнее, обходит защиты)
    2. Если Playwright недоступен — используем aiohttp
    3. Retry логика на каждом уровне
    """
    
    # === СТРАТЕГИЯ 1: Playwright первый (рекомендуется) ===
    if USE_PLAYWRIGHT_FIRST and browser_context:
        # Пробуем Playwright с retry
        for attempt in range(2):  # 2 попытки для Playwright
            content, error = await render_with_browser_stealth(url, browser_context, attempt)
            
            if content and len(content) >= MIN_CONTENT_LENGTH:
                # Проверяем на защиту
                if not is_protection_page(content):
                    return (content, "")
            
            # Если таймаут или нет соединения — повторяем
            if error in ["таймаут", "нет_соединения"] and attempt < 1:
                await asyncio.sleep(RETRY_DELAYS[0])
                continue
            
            # Если Cloudflare или другая защита — выходим
            if content and is_protection_page(content):
                return (None, "cloudflare")
            
            # Если ошибка не таймаут — пробуем aiohttp как fallback
            break
        
        # Fallback на aiohttp если Playwright не помог
        if error and error not in ["cloudflare", "доступ_запрещён"]:
            aio_content, aio_error = await fetch_with_aiohttp(url, session)
            if aio_content and len(aio_content) >= MIN_CONTENT_LENGTH:
                if not is_protection_page(aio_content):
                    return (aio_content, "")
            # Возвращаем исходную ошибку от Playwright
            return (content, error)
        
        return (content, error)
    
    # === СТРАТЕГИЯ 2: aiohttp первый (старая логика) ===
    else:
        content, error = await fetch_with_aiohttp(url, session)
        
        if content and len(content) >= MIN_CONTENT_LENGTH:
            if not is_protection_page(content):
                return (content, "")
        
        # Фолбэк на Playwright
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


print("✅ Загрузка контента настроена (Playwright-first режим)")

# ============================================================================
# LLM АНАЛИЗ
# ============================================================================

async def call_llm_async(prompt: str, session: aiohttp.ClientSession, max_tokens: int = 500) -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    
    for attempt in range(2):
        try:
            async with llm_semaphore:
                async with session.post(LLM_API_URL, headers=headers, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=90)) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result['choices'][0]['message']['content'].strip()
        except Exception:
            if attempt < 1:
                await asyncio.sleep(3)
            else:
                return None
    return None


def parse_llm_json_response(response: str, competitor_name: str) -> Dict[str, Any]:
    default_result = {
        "category": CATEGORY_TECHNICAL,
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
        
        if result.get("category") not in [CATEGORY_PRODUCTS, CATEGORY_PRICES, CATEGORY_NEWS, CATEGORY_TECHNICAL]:
            result["category"] = CATEGORY_TECHNICAL
        
        valid_tags = [t for t in result.get("tags", []) if t in TAGS]
        result["tags"] = valid_tags[:3]
        
        summary = result.get("summary", "")
        
        summary = re.sub(r'```.*', '', summary)
        summary = re.sub(r'\{.*', '', summary)
        summary = summary.strip()
        
        uninformative_patterns = [
            r'^обновлён\s*(контент|содержимое)?\s*сайт',
            r'^контент\s*сайта\s*(был\s*)?(обновлён|изменён)',
            r'^сайт\s*(был\s*)?(обновлён|изменён)',
            r'^изменения\s*на\s*сайте',
            r'^зафиксированы\s*изменения',
            r'^обнаружены\s*изменения',
            r'^технические\s*изменения',
            r'^незначительные\s*изменения',
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
            result["category"] = CATEGORY_TECHNICAL
            return result
        
        result["summary"] = summary
        result["is_meaningful"] = True
        
        return result
        
    except json.JSONDecodeError:
        summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', response)
        if summary_match and len(summary_match.group(1)) > 40:
            return {
                "category": CATEGORY_TECHNICAL,
                "tags": [],
                "summary": summary_match.group(1),
                "is_meaningful": True
            }
        return default_result


async def analyze_changes_async(competitor_name: str, new_content: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
    prompt = f"""Ты анализируешь ИЗМЕНЕНИЯ на сайте компании "{competitor_name}" в сфере ГЛОНАСС/GPS мониторинга транспорта.

ТЕКУЩИЙ КОНТЕНТ САЙТА:
{new_content[:3000]}

ЗАДАЧА: Найди что КОНКРЕТНО изменилось и верни JSON.

КАТЕГОРИИ (выбери ОДНУ, приоритет сверху вниз):

1. "products" — ВЫБИРАЙ ЭТУ если есть:
   - Новый продукт, устройство, терминал, трекер, тахограф
   - Новая услуга, сервис, функция, модуль, раздел сайта с функционалом
   - Новое ПО, приложение, платформа, система
   - Обновление существующего продукта с новыми возможностями
   ПРИМЕРЫ: "Появился новый трекер X", "Запущен новый модуль мониторинга", "Добавлен раздел с новой услугой"

2. "prices" — ВЫБИРАЙ ЭТУ если есть:
   - Акция, скидка, распродажа, спецпредложение
   - Изменение цен, новые тарифы
   - Бесплатный период, бонусы
   ПРИМЕРЫ: "Скидка 30% на терминалы", "Новые тарифы на мониторинг"

3. "news" — ВЫБИРАЙ ЭТУ если есть:
   - Новость, объявление, пресс-релиз
   - Партнёрство, сотрудничество, интеграция
   - Событие, конференция, выставка
   - Изменения в законодательстве, сертификация
   - Уход с рынка, закрытие, важное объявление
   ПРИМЕРЫ: "Компания объявила о партнёрстве с X", "Wialon уходит с рынка РФ"

4. "technical" — ВЫБИРАЙ ЭТУ ТОЛЬКО если:
   - Изменился только дизайн сайта без нового функционала
   - Изменилась только структура/навигация
   - НЕТ ничего из категорий выше
   ВАЖНО: Если появился новый раздел С ФУНКЦИОНАЛОМ — это "products", не "technical"!

ФОРМАТ ОТВЕТА (только JSON):
{{
    "category": "products|prices|news|technical",
    "tags": ["тег1", "тег2"],
    "summary": "Конкретное описание: ЧТО появилось/изменилось, КАК называется, ДЛЯ ЧЕГО предназначено (2-3 предложения)"
}}

ТЕГИ (выбери 1-3 подходящих): новый_продукт, оборудование, тахографы, мониторинг, ПО, акция, скидка, бесплатно, новость, важное, партнёрство, законодательство, wialon, глонасс

ПРАВИЛА SUMMARY:
✓ Пиши конкретно: "Появился терминал Omnicomm X5 с поддержкой 4G"
✓ Указывай названия: "Запущен модуль «Пассажирские перевозки»"
✓ Объясняй назначение: "для мониторинга пассажирского транспорта"
✗ НЕ пиши общие фразы: "Обновлён контент сайта", "Компания предлагает услуги"
✗ НЕ описывай что компания делает в целом

Если не можешь найти КОНКРЕТНОЕ изменение — верни category "technical" и в summary напиши что именно изменилось на сайте (структура, дизайн, тексты).

Ответь ТОЛЬКО JSON без пояснений."""

    response = await call_llm_async(prompt, session, max_tokens=600)
    return parse_llm_json_response(response, competitor_name)

print("✅ LLM анализ настроен")

# ============================================================================
# PDF ГЕНЕРАЦИЯ
# ============================================================================

def generate_pdf_report(
    report_date: str,
    total_checked: int,
    categorized_changes: Dict[str, List[Dict]],
    failed_sites: List[Dict]
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
    
    total_changes = sum(len(v) for v in categorized_changes.values())
    total_ok = total_checked - len(failed_sites)
    
    stats = f"📊 Проверено: {total_checked} | ✅ Успешно: {total_ok} | 🔄 Важные изменения: {total_changes} | ⚠️ Проблемы: {len(failed_sites)}"
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
        
        success_rate = round(total_ok / total_checked * 100, 1) if total_checked > 0 else 0
        content.append(Paragraph(f"✅ Успешно проверено: <b>{total_ok}</b> ({success_rate}%)", styles['stats']))
        
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
            pct = round(len(sites) / total_checked * 100, 1)
            content.append(Paragraph(f"{label}: <b>{len(sites)}</b> ({pct}%)", styles['stats']))
    
    content.append(Spacer(1, 10))
    
    # === ПРОДУКТЫ ===
    if categorized_changes[CATEGORY_PRODUCTS]:
        content.append(Paragraph("🏷️ НОВЫЕ ПРОДУКТЫ И УСЛУГИ", styles['section']))
        for i, item in enumerate(categorized_changes[CATEGORY_PRODUCTS], 1):
            content.append(Paragraph(f"{i}. {item['competitor']} — {item['url']}", styles['company']))
            content.append(Paragraph(item['summary'], styles['summary']))
            if item.get('tags'):
                tags_str = ' '.join([f"#{t}" for t in item['tags']])
                content.append(Paragraph(tags_str, styles['tags']))
    
    # === ЦЕНЫ ===
    if categorized_changes[CATEGORY_PRICES]:
        content.append(Paragraph("💰 ЦЕНЫ И АКЦИИ", styles['section']))
        for i, item in enumerate(categorized_changes[CATEGORY_PRICES], 1):
            content.append(Paragraph(f"{i}. {item['competitor']} — {item['url']}", styles['company']))
            content.append(Paragraph(item['summary'], styles['summary']))
            if item.get('tags'):
                tags_str = ' '.join([f"#{t}" for t in item['tags']])
                content.append(Paragraph(tags_str, styles['tags']))
    
    # === НОВОСТИ ===
    if categorized_changes[CATEGORY_NEWS]:
        content.append(Paragraph("📰 НОВОСТИ", styles['section']))
        for i, item in enumerate(categorized_changes[CATEGORY_NEWS], 1):
            content.append(Paragraph(f"{i}. {item['competitor']} — {item['url']}", styles['company']))
            content.append(Paragraph(item['summary'], styles['summary']))
            if item.get('tags'):
                tags_str = ' '.join([f"#{t}" for t in item['tags']])
                content.append(Paragraph(tags_str, styles['tags']))
    
    # === ПРОБЛЕМЫ ===
    if failed_sites:
        content.append(Paragraph("⚠️ НЕ УДАЛОСЬ ПРОВЕРИТЬ", styles['section']))
        
        by_reason = {}
        for site in failed_sites:
            reason = site.get('error_type', 'другое')
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(site)
        
        reason_labels = {
            "таймаут": "⏱️ Таймаут",
            "нет_соединения": "🔌 Нет соединения",
            "cloudflare": "🛡️ Защита Cloudflare",
            "доступ_запрещён": "🚫 Доступ запрещён",
            "не_найден": "❓ Страница не найдена",
            "ошибка_сервера": "💥 Ошибка сервера",
            "нечитаемый": "📄 Нечитаемый контент",
            "мало_контента": "📄 Мало контента",
            "ошибка": "⚠️ ошибка",
        }
        
        sorted_reasons = sorted(by_reason.items(), key=lambda x: -len(x[1]))
        for reason, sites in sorted_reasons:
            label = reason_labels.get(reason, reason)
            names = []
            for site in sites:
                name = site.get('competitor', 'Неизвестный')
                if len(names) >= 10:
                    names.append(f"... и ещё {len(sites) - 10}")
                    break
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
            'raw_change_data': raw_content[:50000] if raw_content else None,
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

print("✅ Supabase настроен")

# ============================================================================
# СКАНИРОВАНИЕ КОНКУРЕНТА
# ============================================================================

async def scan_competitor_async(competitor: Dict, report_id: str, scan_date: str,
                                http_session: aiohttp.ClientSession, browser_context) -> Dict[str, Any]:
    competitor_id = competitor['id']
    competitor_name = competitor.get('name', 'Unknown')
    competitor_url = competitor.get('url', '')

    print(f"🔍 {competitor_name}")

    previous_hash = get_previous_hash(competitor_id)

    content, error_type = await fetch_website_content_async(competitor_url, http_session, browser_context)

    if not content:
        return {
            'competitor': competitor_name,
            'url': competitor_url,
            'error_type': error_type or 'ошибка',
            'is_error': True
        }

    if is_protection_page(content):
        scan_id = generate_unique_id("scan_")
        create_scan_result(scan_id, scan_date, competitor_id, "PROTECTION_PAGE", False)
        return {
            'competitor': competitor_name,
            'url': competitor_url,
            'error_type': 'cloudflare',
            'is_error': True
        }

    if is_unreadable_content(content):
        scan_id = generate_unique_id("scan_")
        create_scan_result(scan_id, scan_date, competitor_id, "UNREADABLE", False)
        return {
            'competitor': competitor_name,
            'url': competitor_url,
            'error_type': 'нечитаемый',
            'is_error': True
        }

    normalized = normalize_content_for_hash(content)
    new_hash = calculate_hash(normalized)
    
    content_changed = previous_hash and new_hash != previous_hash

    result = None
    llm_summary = ""

    if content_changed:
        print(f"   🔔 Изменения: {competitor_name}")
        
        analysis = await analyze_changes_async(competitor_name, content, http_session)
        
        if analysis.get("is_meaningful"):
            result = {
                'competitor': competitor_name,
                'url': competitor_url,
                'category': analysis['category'],
                'summary': analysis['summary'],
                'tags': analysis['tags'],
                'is_error': False,
                'is_meaningful': True
            }
            llm_summary = analysis['summary']
        else:
            result = None
            llm_summary = analysis.get('summary', 'Обновлён контент')
            print(f"   ⏭️ Пропуск неинформативного изменения: {competitor_name}")

    scan_id = generate_unique_id("scan_")
    scan_result_id = create_scan_result(
        scan_id, scan_date, competitor_id, new_hash, content_changed,
        content if content_changed else "", llm_summary,
        report_id if content_changed and result else None
    )
    
    if scan_result_id:
        update_competitor_last_scan(competitor_id, scan_result_id)

    return result

print("✅ Сканирование настроено")

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

async def run_monitoring_async():
    print("🚀 Запуск мониторинга...")
    start_time = time.time()
    
    init_semaphores()
    send_telegram_message("🚀 <b>Запуск мониторинга конкурентов</b>")

    current_date = datetime.now().strftime("%Y-%m-%d")
    report_id = generate_unique_id("report_")
    summary_report_id = create_summary_report(report_id, current_date)

    if not summary_report_id:
        send_telegram_message("❌ Ошибка создания отчёта")
        return

    try:
        competitors = supabase.table('competitors').select('*').execute().data
    except Exception as e:
        send_telegram_message(f"❌ Ошибка: {str(e)[:200]}")
        return

    total_competitors = len(competitors)
    print(f"🌐 Конкурентов: {total_competitors}")

    categorized_changes = {
        CATEGORY_PRODUCTS: [],
        CATEGORY_PRICES: [],
        CATEGORY_NEWS: [],
        CATEGORY_TECHNICAL: []
    }
    failed_sites = []

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, ssl=False)
    
    async with aiohttp.ClientSession(connector=connector) as http_session:
        async with async_playwright() as p:
            # Запуск браузера со stealth-настройками
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                    '--disable-blink-features=AutomationControlled',  # Скрываем автоматизацию
                ]
            )
            
            browser_context = await browser.new_context(
                user_agent=get_random_user_agent(),
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True,
                locale='ru-RU',
                timezone_id='Europe/Moscow',
                # Дополнительные stealth параметры
                extra_http_headers={
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                }
            )
            
            tasks = [
                scan_competitor_async(c, summary_report_id, current_date, http_session, browser_context)
                for c in competitors
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            await browser_context.close()
            await browser.close()

    for result in results:
        if isinstance(result, Exception) or not result:
            continue
        
        if result.get('is_error'):
            failed_sites.append(result)
        elif result.get('is_meaningful', True):
            category = result.get('category', CATEGORY_TECHNICAL)
            if category in categorized_changes:
                categorized_changes[category].append(result)

    elapsed = int(time.time() - start_time)
    print(f"⏱️ Время: {elapsed} сек")

    total_changes = sum(len(v) for v in categorized_changes.values())
    total_ok = total_competitors - len(failed_sites)
    
    # === СОХРАНЯЕМ СТАТИСТИКУ В БД ===
    update_summary_report_with_stats(
        summary_report_id,
        total_sites=total_competitors,
        successful_sites=total_ok,
        changes_count=total_changes,
        problems_count=len(failed_sites),
        duration_seconds=elapsed
    )

    pdf_path = generate_pdf_report(current_date, total_competitors, categorized_changes, failed_sites)

    # Группируем ошибки по типам для статистики
    errors_by_type = {}
    for site in failed_sites:
        error_type = site.get('error_type', 'другое')
        errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1
    
    # Формируем строку статистики ошибок
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
    
    # Сортируем по количеству
    sorted_errors = sorted(errors_by_type.items(), key=lambda x: -x[1])
    for error_type, count in sorted_errors:
        label = error_labels.get(error_type, error_type)
        error_stats_lines.append(f"   {label}: {count}")
    
    error_stats_text = "\n".join(error_stats_lines) if error_stats_lines else "   Нет данных"

    success_rate = round(total_ok / total_competitors * 100, 1) if total_competitors > 0 else 0

    msg = f"""📊 <b>Мониторинг завершён</b>

📅 Дата: {current_date}
⏱️ Время: {elapsed} сек
🌐 Проверено: <b>{total_competitors}</b>

✅ <b>Успешно: {total_ok}</b> ({success_rate}%)

🔄 <b>Важные изменения: {total_changes}</b>
   🏷️ Продукты: {len(categorized_changes[CATEGORY_PRODUCTS])}
   💰 Цены/акции: {len(categorized_changes[CATEGORY_PRICES])}
   📰 Новости: {len(categorized_changes[CATEGORY_NEWS])}
   🔧 Технические: {len(categorized_changes[CATEGORY_TECHNICAL])}

⚠️ <b>Проблемы: {len(failed_sites)}</b>
{error_stats_text}

📎 Подробный отчёт во вложении"""

    send_telegram_document(pdf_path, msg)
    
    try:
        os.remove(pdf_path)
    except:
        pass

    print("✅ Готово!")


def run_monitoring_system():
    asyncio.run(run_monitoring_async())

print("✅ Система готова")

if __name__ == "__main__":
    run_monitoring_system()
