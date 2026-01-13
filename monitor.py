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

# === ОБНОВЛЁННЫЕ ТАЙМАУТЫ И RETRY ===
REQUEST_TIMEOUT = 45  # было 35
PLAYWRIGHT_TIMEOUT = 50000  # было 35000
MAX_RETRIES = 3  # было 2
RETRY_DELAYS = [2, 5, 10]  # прогрессивные задержки между попытками

MIN_CONTENT_LENGTH = 200

# === РОТАЦИЯ USER-AGENT ===
USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Firefox Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

# Для обратной совместимости
USER_AGENT = USER_AGENTS[0]

MAX_CONCURRENT_REQUESTS = 15
MAX_CONCURRENT_BROWSER = 3
MAX_CONCURRENT_LLM = 5

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

print("✅ Утилиты загружены")

# ============================================================================
# ЗАГРУЗКА КОНТЕНТА
# ============================================================================

def get_headers_for_url(url: str, attempt: int = 0) -> dict:
    """Генерирует заголовки с ротацией User-Agent и Referer"""
    user_agent = USER_AGENTS[attempt % len(USER_AGENTS)] if attempt > 0 else get_random_user_agent()
    
    # Извлекаем домен для Referer
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
    
    # Добавляем Referer на повторных попытках (помогает с 403)
    if attempt > 0:
        headers['Referer'] = base_url + '/'
        headers['Origin'] = base_url
    
    return headers


async def fetch_with_aiohttp(url: str, session: aiohttp.ClientSession) -> Tuple[Optional[str], str]:
    """Асинхронная загрузка через aiohttp с улучшенной обработкой ошибок"""
    
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
                    
                    # Обработка 403 - пробуем ещё раз с другими заголовками
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
                    
                    # Декодируем
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
                    
                    # Мало контента - пробуем ещё
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
                
        except aiohttp.ClientConnectorError as e:
            last_error = "нет_соединения"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 10
                await asyncio.sleep(delay)
                continue
                
        except aiohttp.ClientResponseError as e:
            last_error = "ошибка"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else 5
                await asyncio.sleep(delay)
                continue
                
        except Exception as e:
            last_error = "ошибка"
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2)
                continue
    
    return (None, last_error)


async def render_with_browser(url: str, browser_context) -> Optional[str]:
    """Рендеринг JavaScript-страниц через Playwright"""
    try:
        async with browser_semaphore:
            page = await browser_context.new_page()
            try:
                # Блокируем тяжёлые ресурсы
                await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,mp4,webm}", lambda route: route.abort())
                
                await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until='networkidle')
                await page.wait_for_timeout(2000)  # Даём больше времени на загрузку JS
                
                html = await page.content()
                soup = BeautifulSoup(html, 'lxml')
                text = clean_html_content(soup)
                
                await page.close()
                return text if len(text) >= MIN_CONTENT_LENGTH else None
            except Exception as e:
                try:
                    await page.close()
                except:
                    pass
                return None
    except Exception as e:
        return None


async def fetch_website_content_async(url: str, session: aiohttp.ClientSession, browser_context=None) -> Tuple[Optional[str], str]:
    """Загрузка контента с фолбэком на браузер"""
    
    # Сначала пробуем обычный HTTP
    content, error = await fetch_with_aiohttp(url, session)
    
    if content and len(content) >= MIN_CONTENT_LENGTH:
        return (content, "")
    
    # Если не получилось или мало контента - пробуем браузер
    if browser_context and (not content or error in ["мало_контента", "таймаут", "доступ_запрещён"]):
        browser_content = await render_with_browser(url, browser_context)
        if browser_content:
            return (browser_content, "")
    
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
        except Exception as e:
            if attempt < 1:
                await asyncio.sleep(3)
            else:
                return None
    return None


def parse_llm_json_response(response: str, competitor_name: str) -> Dict[str, Any]:
    default_result = {
        "category": CATEGORY_TECHNICAL,
        "tags": [],
        "summary": f"Зафиксированы изменения на сайте {competitor_name}.",
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
        if not summary or len(summary) < 30:
            return default_result
        
        summary = re.sub(r'```.*', '', summary)
        summary = re.sub(r'\{.*', '', summary)
        result["summary"] = summary.strip()
        result["is_meaningful"] = True
        
        return result
        
    except json.JSONDecodeError:
        summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', response)
        if summary_match and len(summary_match.group(1)) > 30:
            return {
                "category": CATEGORY_TECHNICAL,
                "tags": [],
                "summary": summary_match.group(1),
                "is_meaningful": True
            }
        return default_result


async def analyze_changes_async(competitor_name: str, new_content: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
    prompt = f"""Ты анализируешь ИЗМЕНЕНИЯ на сайте компании "{competitor_name}".

ВАЖНО: Не описывай что компания делает в целом! Опиши только что НОВОГО появилось или ИЗМЕНИЛОСЬ.

ТЕКУЩИЙ КОНТЕНТ САЙТА:
{new_content[:2500]}

ЗАДАЧА: Определи что ИЗМЕНИЛОСЬ и верни JSON:

{{
    "category": "products|prices|news|technical",
    "tags": ["тег1", "тег2"],
    "summary": "Что конкретно изменилось или появилось нового (3-4 предложения)"
}}

КАТЕГОРИИ:
- "products" — НОВЫЕ продукты, услуги, оборудование
- "prices" — НОВЫЕ акции, скидки, изменение цен
- "news" — НОВОСТИ: события, объявления, партнёрства
- "technical" — технические изменения сайта

ТЕГИ: новый_продукт, оборудование, тахографы, мониторинг, ПО, акция, скидка, бесплатно, новость, важное, партнёрство, законодательство, wialon, глонасс

ПРАВИЛА:
- Пиши "Появился новый продукт X", "Запущена акция Y"
- НЕ пиши "Компания предлагает...", "Система позволяет..."

Ответь ТОЛЬКО JSON."""

    response = await call_llm_async(prompt, session)
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
    }
    
    content = []
    
    content.append(Paragraph("Отчёт мониторинга конкурентов", styles['title']))
    content.append(Paragraph(f"Дата: {report_date}", styles['subtitle']))
    
    total_changes = sum(len(v) for v in categorized_changes.values())
    stats = f"📊 Проверено: {total_checked} | ✅ Изменения: {total_changes} | ⚠️ Проблемы: {len(failed_sites)}"
    content.append(Paragraph(stats, styles['subtitle']))
    content.append(Spacer(1, 10))
    
    sections = [
        (CATEGORY_PRODUCTS, "🏷️ НОВЫЕ ПРОДУКТЫ И УСЛУГИ"),
        (CATEGORY_PRICES, "💰 ЦЕНЫ И АКЦИИ"),
        (CATEGORY_NEWS, "📰 НОВОСТИ"),
        (CATEGORY_TECHNICAL, "🔧 ТЕХНИЧЕСКИЕ ИЗМЕНЕНИЯ"),
    ]
    
    for category, title in sections:
        items = categorized_changes.get(category, [])
        if not items:
            continue
            
        content.append(Paragraph(title, styles['section']))
        
        for i, item in enumerate(items, 1):
            name = item.get('competitor', '')
            url = item.get('url', '')
            summary = item.get('summary', '')
            tags = item.get('tags', [])
            
            if url:
                company_text = f"{i}. <b>{name}</b> — <a href='{url}' color='blue'>{url}</a>"
            else:
                company_text = f"{i}. <b>{name}</b>"
            content.append(Paragraph(company_text, styles['company']))
            
            if summary:
                content.append(Paragraph(summary, styles['summary']))
            
            if tags:
                tag_parts = [f"<font color='{TAGS.get(tag, '#999')}'><b>#{tag}</b></font>" for tag in tags]
                content.append(Paragraph(" ".join(tag_parts), styles['tags']))
    
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
        
        for reason, sites in by_reason.items():
            label = reason_labels.get(reason, f"❓ {reason}")
            names = []
            for site in sites:
                name = site.get('competitor', '')
                url = site.get('url', '')
                if url:
                    names.append(f"<a href='{url}' color='blue'>{name}</a>")
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

def update_summary_report(report_id, text):
    try:
        supabase.table('summary_reports').update({'overall_llm_report': text}).eq('id', report_id).execute()
    except:
        pass

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
                'is_error': False
            }
            llm_summary = analysis['summary']
        else:
            result = {
                'competitor': competitor_name,
                'url': competitor_url,
                'category': CATEGORY_TECHNICAL,
                'summary': "Обновлён контент сайта",
                'tags': [],
                'is_error': False
            }
            llm_summary = "Обновлён контент"

    scan_id = generate_unique_id("scan_")
    scan_result_id = create_scan_result(
        scan_id, scan_date, competitor_id, new_hash, content_changed,
        content if content_changed else "", llm_summary,
        report_id if content_changed else None
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
            browser = await p.chromium.launch(headless=True)
            browser_context = await browser.new_context(
                user_agent=get_random_user_agent(),
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
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
        else:
            category = result.get('category', CATEGORY_TECHNICAL)
            if category in categorized_changes:
                categorized_changes[category].append(result)

    elapsed = time.time() - start_time
    print(f"⏱️ Время: {elapsed:.0f} сек")

    total_changes = sum(len(v) for v in categorized_changes.values())
    update_summary_report(summary_report_id, f"Изменения: {total_changes}")

    pdf_path = generate_pdf_report(current_date, total_competitors, categorized_changes, failed_sites)

    msg = f"""📊 <b>Мониторинг завершён</b>

📅 Дата: {current_date}
⏱️ Время: {elapsed:.0f} сек
🌐 Проверено: <b>{total_competitors}</b>

✅ <b>Изменения: {total_changes}</b>
   🏷️ Продукты: {len(categorized_changes[CATEGORY_PRODUCTS])}
   💰 Цены/акции: {len(categorized_changes[CATEGORY_PRICES])}
   📰 Новости: {len(categorized_changes[CATEGORY_NEWS])}
   🔧 Технические: {len(categorized_changes[CATEGORY_TECHNICAL])}

⚠️ <b>Не удалось проверить: {len(failed_sites)}</b>

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
