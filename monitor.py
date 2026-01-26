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
from datetime import datetime, timedelta
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
TELEGRAM_GROUP_CHAT_ID = os.environ.get("TELEGRAM_GROUP_CHAT_ID")

LLM_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"

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
MAX_CONCURRENT_LLM = 5

# Batch-обработка для стабильности
BATCH_SIZE = 50
BATCH_DELAY = 3  # секунд между батчами

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

def send_app_button(chat_id: str = None) -> bool:
    """Отправляет кнопку для открытия Mini App"""
    if not TELEGRAM_BOT_TOKEN:
        return False
    target_chat_id = chat_id or TELEGRAM_GROUP_CHAT_ID
    if not target_chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        keyboard = {
            "inline_keyboard": [[{
                "text": "📊 Открыть Competitor Monitor",
                "web_app": {"url": "https://nadymovds.github.io/competitor-monitor/"}
            }]]
        }
        requests.post(url, json={
            "chat_id": target_chat_id, 
            "text": "🔗 <b>Competitor Monitor</b>\n\nНажмите кнопку ниже, чтобы открыть приложение для мониторинга конкурентов.", 
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

        # Очищаем summary от артефактов
        summary = re.sub(r'```.*', '', summary)
        summary = re.sub(r'\{.*', '', summary)
        summary = summary.strip()

        # Проверка на мусорные символы (если более 10% непечатных — отклоняем)
        non_printable = sum(1 for c in summary if ord(c) < 32 or ord(c) > 65535)
        if summary and non_printable > len(summary) * 0.1:
            result["is_meaningful"] = False
            result["summary"] = "Ошибка анализа контента"
            result["category"] = CATEGORY_TECHNICAL
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

        # Проверка релевантности
        relevant_keywords = ['транспорт', 'мониторинг', 'глонасс', 'gps', 'трекер',
                             'тахограф', 'топлив', 'автопарк', 'навигац', 'телематик',
                             'датчик', 'wialon', 'слежен', 'контрол']

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
                "category": CATEGORY_TECHNICAL,
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

    # Сравнительный промпт
    prompt = f"""Сравни СТАРУЮ и НОВУЮ версию сайта компании "{competitor_name}" в сфере ГЛОНАСС/GPS мониторинга транспорта.

СТАРАЯ ВЕРСИЯ:
{previous_content[:2000]}

НОВАЯ ВЕРСИЯ:
{new_content[:2000]}

ЗАДАЧА: Найди ЧТО КОНКРЕТНО ИЗМЕНИЛОСЬ между версиями.

ИГНОРИРУЙ технические изменения:
- Изменение дат, счётчиков посетителей
- Изменение порядка элементов
- Изменение дизайна без нового контента
- Незначительные текстовые правки

ФИКСИРУЙ важные изменения:
- Новый продукт, услуга, функция
- Новая цена, акция, скидка
- Новость, анонс, партнёрство

ВАЖНЫЕ ПРАВИЛА:
- Отвечай ТОЛЬКО на русском языке
- Если важных изменений НЕТ — верни is_meaningful: false
- Описывай только реальные изменения, не выдумывай

КАТЕГОРИИ (выбери ОДНУ):
1. "products" — новый продукт, устройство, трекер, тахограф, услуга, сервис, ПО, платформа
2. "prices" — акция, скидка, спецпредложение, изменение цен, бесплатный период
3. "news" — новость, партнёрство, событие, изменения в законодательстве
4. "technical" — только дизайн/структура сайта без нового контента (или нет изменений)

ФОРМАТ ОТВЕТА (только JSON, без пояснений):
{{
    "category": "products|prices|news|technical",
    "summary": "Описание что ИЗМЕНИЛОСЬ (не что есть на сайте, а что НОВОГО появилось). 2-3 предложения.",
    "tags": ["тег1", "тег2"],
    "is_meaningful": true/false
}}

ТЕГИ: новый_продукт, оборудование, тахографы, мониторинг, ПО, акция, скидка, бесплатно, новость, важное, партнёрство, законодательство, wialon, глонасс"""

    response = await call_llm_async(prompt, session, max_tokens=600)
    return parse_llm_json_response(response, competitor_name)

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
    first_scans_count: int = 0
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
    total_ok = total_urls - len(failed_sites)

    stats = f"📊 Конкурентов: {total_competitors} | 🔗 URL: {total_urls} | ✅ Успешно: {total_ok} | 🔄 Изменения: {total_changes} | 🔁 Дубликаты: {duplicates_count} | 🆕 Первые: {first_scans_count} | ⚠️ Проблемы: {len(failed_sites)}"
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
        (CATEGORY_NEWS, "📰 НОВОСТИ"),
    ]
    
    for category, title in sections:
        items = categorized_changes.get(category, [])
        if not items:
            continue

        content.append(Paragraph(title, styles['section']))

        for i, item in enumerate(items, 1):
            # Используем display_name если доступен (включает label URL)
            name = item.get('display_name') or item.get('competitor', '')
            url = item.get('url', '')
            summary = item.get('summary', '')
            tags = item.get('tags', [])
            
            # === КЛИКАБЕЛЬНАЯ ССЫЛКА ===
            if url:
                # Добавляем https:// если нет
                full_url = url if url.startswith('http') else f'https://{url}'
                company_text = f"{i}. <b>{name}</b> — <a href='{full_url}' color='blue'>{full_url}</a>"
            else:
                company_text = f"{i}. <b>{name}</b>"
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


def save_change(competitor_id: str, category: str, summary: str, tags: List[str], report_id: str, content_hash: str) -> bool:
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
            'report_id': report_id
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
    scanned_url: str = None
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
            'scanned_url': scanned_url
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

        if analysis.get("is_meaningful"):
            llm_summary = analysis['summary']

            # Сохраняем изменение с привязкой к URL
            if url_id:
                save_change_for_url(
                    competitor_id=competitor_id,
                    category=analysis['category'],
                    summary=analysis['summary'],
                    tags=analysis['tags'],
                    report_id=report_id,
                    content_hash=content_hash,
                    url_id=url_id,
                    scanned_url=url
                )
            else:
                save_change(
                    competitor_id=competitor_id,
                    category=analysis['category'],
                    summary=analysis['summary'],
                    tags=analysis['tags'],
                    report_id=report_id,
                    content_hash=content_hash
                )

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
        # Загружаем конкурентов вместе с их URL
        competitors = supabase.table('competitors').select(
            '*, competitor_urls(id, url, label, is_active, sort_order)'
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

    total_urls = len(scan_tasks_list)
    print(f"🌐 Конкурентов: {total_competitors}, URL для проверки: {total_urls}")

    categorized_changes = {
        CATEGORY_PRODUCTS: [],
        CATEGORY_PRICES: [],
        CATEGORY_NEWS: [],
        CATEGORY_TECHNICAL: []
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

            # Batch-обработка для стабильности
            results = []
            total_batches = (len(scan_tasks_list) + BATCH_SIZE - 1) // BATCH_SIZE

            for batch_idx in range(total_batches):
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min(start_idx + BATCH_SIZE, len(scan_tasks_list))
                batch = scan_tasks_list[start_idx:end_idx]

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

    elapsed = int(time.time() - start_time)
    print(f"⏱️ Время: {elapsed} сек")

    total_changes = sum(len(v) for v in categorized_changes.values())
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

    pdf_path = generate_pdf_report(current_date, total_competitors, total_urls, categorized_changes, failed_sites, duplicates_count, first_scans_count)

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

    msg = f"""📊 <b>Мониторинг завершён</b>

📅 Дата: {current_date}
⏱️ Время: {elapsed} сек
🌐 Конкурентов: <b>{total_competitors}</b>
🔗 URL проверено: <b>{total_urls}</b>

✅ <b>Успешно: {total_ok}</b> ({success_rate}%)

🔄 <b>Важные изменения: {total_changes}</b>
   🏷️ Продукты: {len(categorized_changes[CATEGORY_PRODUCTS])}
   💰 Цены/акции: {len(categorized_changes[CATEGORY_PRICES])}
   📰 Новости: {len(categorized_changes[CATEGORY_NEWS])}
   🔧 Технические: {len(categorized_changes[CATEGORY_TECHNICAL])}

🔁 <b>Пропущено дубликатов: {duplicates_count}</b>
🆕 <b>Первых сканирований: {first_scans_count}</b>

⚠️ <b>Проблемы: {len(failed_sites)}</b>
{error_stats_text}

📎 Подробный отчёт во вложении"""

    # Добавляем краткий список изменений если их не много
    if total_changes > 0 and total_changes <= 5:
        changes_text = "\n\n📋 <b>Изменения:</b>"
        for cat in [CATEGORY_PRODUCTS, CATEGORY_PRICES, CATEGORY_NEWS]:
            for item in categorized_changes.get(cat, []):
                name = item.get('display_name') or item.get('competitor', '')
                summary = item.get('summary', '')[:100]
                if len(item.get('summary', '')) > 100:
                    summary += '...'
                changes_text += f"\n• <b>{name}</b>: {summary}"
        msg += changes_text

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
