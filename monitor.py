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
import ssl
import aiohttp
import asyncio
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
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

print("✅ Зависимости импортированы")

# ============================================================================
# ЧАСТЬ 2: Конфигурация и константы
# ============================================================================

# --- Credentials из переменных окружения ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- OpenRouter LLM ---
LLM_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- Настройки ---
REQUEST_TIMEOUT = 35
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MIN_CONTENT_LENGTH = 300
PLAYWRIGHT_TIMEOUT = 35000
MAX_RETRIES = 2

# --- Параллельность ---
MAX_CONCURRENT_REQUESTS = 15  # Одновременных HTTP запросов
MAX_CONCURRENT_BROWSER = 3    # Одновременных браузеров (тяжёлые)
MAX_CONCURRENT_LLM = 5        # Одновременных LLM запросов

# --- Категории изменений ---
CATEGORY_PRODUCTS = "products"
CATEGORY_PRICES = "prices"
CATEGORY_NEWS = "news"
CATEGORY_TECHNICAL = "technical"
CATEGORY_UNREADABLE = "unreadable"

# --- Теги ---
TAGS = {
    "новый_продукт": {"color": "#4CAF50"},
    "оборудование": {"color": "#2196F3"},
    "тахографы": {"color": "#9C27B0"},
    "мониторинг": {"color": "#00BCD4"},
    "ПО": {"color": "#607D8B"},
    "акция": {"color": "#FF9800"},
    "скидка": {"color": "#F44336"},
    "новая_цена": {"color": "#E91E63"},
    "бесплатно": {"color": "#8BC34A"},
    "новость": {"color": "#3F51B5"},
    "важное": {"color": "#f44336"},
    "партнёрство": {"color": "#009688"},
    "законодательство": {"color": "#795548"},
    "обновление_сайта": {"color": "#9E9E9E"},
    "wialon": {"color": "#FF5722"},
    "глонасс": {"color": "#673AB7"},
}

# Инициализация Supabase клиента
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Семафоры для ограничения параллельности ---
http_semaphore = None
browser_semaphore = None
llm_semaphore = None

def init_semaphores():
    """Инициализирует семафоры (вызывать внутри async контекста)"""
    global http_semaphore, browser_semaphore, llm_semaphore
    http_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    browser_semaphore = asyncio.Semaphore(MAX_CONCURRENT_BROWSER)
    llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

# --- Регистрация русского шрифта для PDF ---
def register_fonts():
    """Регистрирует шрифты с поддержкой кириллицы"""
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]
    
    try:
        if os.path.exists(font_paths[0]):
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_paths[0]))
            if os.path.exists(font_paths[1]):
                pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_paths[1]))
            print("✅ Шрифты DejaVu зарегистрированы")
            return 'DejaVuSans'
    except Exception as e:
        print(f"⚠️ Не удалось зарегистрировать DejaVu: {e}")
    
    print("⚠️ Используется стандартный шрифт Helvetica")
    return 'Helvetica'

FONT_NAME = register_fonts()

print("✅ Конфигурация загружена")

# ============================================================================
# ЧАСТЬ 3: Telegram функции
# ============================================================================

def send_telegram_message(message: str) -> bool:
    """Отправляет сообщение в Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram не настроен")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        print("✅ Сообщение отправлено в Telegram")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {str(e)}")
        return False


def send_telegram_document(file_path: str, caption: str = "") -> bool:
    """Отправляет документ в Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram не настроен")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, files=files, timeout=60)
            response.raise_for_status()
        
        print("✅ Документ отправлен в Telegram")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки документа в Telegram: {str(e)}")
        return False


# ============================================================================
# ЧАСТЬ 4: Утилиты и вспомогательные функции
# ============================================================================

def generate_unique_id(prefix: str = "") -> str:
    """Генерирует уникальный ID с опциональным префиксом"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique = str(uuid.uuid4())[:8]
    return f"{prefix}{timestamp}_{unique}" if prefix else f"{timestamp}_{unique}"


def calculate_hash(content: str) -> str:
    """Вычисляет SHA-256 хеш контента"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def normalize_content_for_hash(content: str) -> str:
    """Нормализует контент перед хешированием - убирает динамические элементы"""
    content = re.sub(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', '', content)
    content = re.sub(r'\d{4}-\d{2}-\d{2}', '', content)
    content = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', '', content)
    content = re.sub(r'202[0-9]|203[0-9]', '', content)
    content = re.sub(r'посетител\w*\s*:?\s*\d+', '', content, flags=re.IGNORECASE)
    content = re.sub(r'онлайн\s*:?\s*\d+', '', content, flags=re.IGNORECASE)
    content = re.sub(r'просмотр\w*\s*:?\s*\d+', '', content, flags=re.IGNORECASE)
    content = ' '.join(content.split())
    return content


def clean_html_content(soup: BeautifulSoup) -> str:
    """Очищает HTML от скриптов, стилей и служебных элементов"""
    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'iframe']):
        element.decompose()
    text = soup.get_text(separator=' ', strip=True)
    text = ' '.join(text.split())
    return text


def is_protection_page(content: str) -> bool:
    """Проверяет, является ли контент страницей защиты"""
    protection_patterns = [
        'cloudflare', 'ray id', 'checking your browser', 'ddos protection',
        'please wait while we verify', 'just a moment', 'enable javascript and cookies',
        'attention required', 'security check', 'access denied',
        'please complete the security check', 'recaptcha', 'hcaptcha',
        'verifying you are human', 'browser verification',
        'защита от ботов', 'проверка браузера', 'подождите, идет проверка',
    ]
    
    content_lower = content.lower()
    for pattern in protection_patterns:
        if pattern in content_lower:
            return True
    
    if len(content) < 1000:
        short_patterns = ['checking', 'verify', 'moment', 'wait']
        if sum(1 for p in short_patterns if p in content_lower) >= 2:
            return True
    
    return False


def is_unreadable_content(content: str) -> bool:
    """Проверяет, является ли контент нечитаемым"""
    if not content or len(content) < 100:
        return True
    
    non_printable = sum(1 for c in content[:1000] if ord(c) > 127 and not c.isalpha())
    if non_printable > len(content[:1000]) * 0.3:
        return True
    
    russian_words = len(re.findall(r'[а-яА-ЯёЁ]{3,}', content[:2000]))
    english_words = len(re.findall(r'[a-zA-Z]{3,}', content[:2000]))
    
    if russian_words + english_words < 20:
        return True
    
    return False


def is_content_insufficient(content: str) -> bool:
    """Проверяет, достаточно ли контента"""
    if len(content) < MIN_CONTENT_LENGTH:
        return True

    spa_patterns = ['<div id="root"></div>', '<div id="app"></div>',
                    'document.getElementById', 'window.__INITIAL_STATE__']

    if len(content) < 500:
        for pattern in spa_patterns:
            if pattern.lower() in content.lower():
                return True
    return False


print("✅ Вспомогательные функции загружены")

# ============================================================================
# ЧАСТЬ 5: Асинхронные функции загрузки контента
# ============================================================================

async def fetch_with_aiohttp(url: str, session: aiohttp.ClientSession) -> Tuple[Optional[str], str]:
    """Асинхронная загрузка страницы через aiohttp"""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            async with http_semaphore:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT), ssl=False) as response:
                    if response.status == 403:
                        return (None, "доступ_запрещён")
                    if response.status == 404:
                        return (None, "страница_не_найдена")
                    if response.status >= 500:
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(2)
                            continue
                        return (None, "ошибка_сервера")
                    
                    response.raise_for_status()
                    
                    # Читаем контент
                    content_bytes = await response.read()
                    
                    # Пробуем декодировать
                    try:
                        content = content_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            content = content_bytes.decode('cp1251')
                        except:
                            content = content_bytes.decode('utf-8', errors='ignore')
                    
                    soup = BeautifulSoup(content, 'lxml')
                    text = clean_html_content(soup)
                    
                    if len(text) >= MIN_CONTENT_LENGTH:
                        return (text, "")
                    
                    # Недостаточно контента
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(1)
                        continue
                    
                    return (text if text else None, "недостаточно_контента")
                    
        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2)
                continue
            return (None, "таймаут")
        except aiohttp.ClientConnectorError:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2)
                continue
            return (None, "нет_соединения")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1)
                continue
            return (None, f"ошибка: {str(e)[:50]}")
    
    return (None, "неизвестная_ошибка")


async def render_with_browser(url: str, browser_context) -> Optional[str]:
    """Рендеринг страницы через браузер"""
    try:
        async with browser_semaphore:
            page = await browser_context.new_page()
            try:
                await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())
                await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until='networkidle')
                await page.wait_for_timeout(1500)
                html_content = await page.content()
                soup = BeautifulSoup(html_content, 'lxml')
                text = clean_html_content(soup)
                await page.close()
                return text if len(text) >= MIN_CONTENT_LENGTH else None
            except Exception as e:
                await page.close()
                return None
    except Exception as e:
        return None


async def fetch_website_content_async(url: str, session: aiohttp.ClientSession, browser_context=None) -> Tuple[Optional[str], str]:
    """Асинхронная загрузка контента с fallback на браузер"""
    # Сначала пробуем aiohttp
    content, error = await fetch_with_aiohttp(url, session)
    
    if content and len(content) >= MIN_CONTENT_LENGTH:
        return (content, "")
    
    # Fallback на браузер если есть контекст и контента мало
    if browser_context and (not content or error == "недостаточно_контента"):
        browser_content = await render_with_browser(url, browser_context)
        if browser_content:
            return (browser_content, "")
    
    return (content, error)


print("✅ Асинхронные функции загрузки загружены")

# ============================================================================
# ЧАСТЬ 6: Функции работы с LLM (OpenRouter)
# ============================================================================

async def call_llm_async(prompt: str, session: aiohttp.ClientSession, max_tokens: int = 400) -> Optional[str]:
    """Асинхронный запрос к LLM"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.5
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
                continue
            return None
    return None


async def analyze_changes_with_category_async(competitor_name: str, new_content: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
    """Асинхронный анализ изменений"""
    
    prompt = f"""Проанализируй контент сайта компании "{competitor_name}" и определи тип изменений.

КОНТЕНТ САЙТА (фрагмент):
{new_content[:2500]}

ЗАДАЧА: Верни JSON в точном формате:
{{
    "category": "products|prices|news|technical",
    "tags": ["тег1", "тег2"],
    "summary": "Подробное описание изменений (3-4 предложения)",
    "is_meaningful": true/false
}}

ПРАВИЛА КАТЕГОРИЗАЦИИ:
- "products" — новые продукты, услуги, оборудование, решения
- "prices" — акции, скидки, изменение цен, спецпредложения  
- "news" — новости компании, события, партнёрства, изменения в законодательстве
- "technical" — обновления сайта, исправления, технические изменения

ДОСТУПНЫЕ ТЕГИ: новый_продукт, оборудование, тахографы, мониторинг, ПО, акция, скидка, новая_цена, бесплатно, новость, важное, партнёрство, законодательство, обновление_сайта, wialon, глонасс

ВАЖНО:
- is_meaningful=false если контент нечитаемый или бессмысленный
- summary должен быть информативным (3-4 предложения)
- Выбери 1-3 подходящих тега

Ответь ТОЛЬКО JSON."""

    response = await call_llm_async(prompt, session)
    
    if not response:
        return {
            "category": CATEGORY_TECHNICAL,
            "tags": [],
            "summary": f"Обнаружены изменения на сайте {competitor_name}.",
            "is_meaningful": False
        }
    
    try:
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r'^```json?\s*', '', json_str)
            json_str = re.sub(r'\s*```$', '', json_str)
        
        result = json.loads(json_str)
        
        if result.get("category") not in [CATEGORY_PRODUCTS, CATEGORY_PRICES, CATEGORY_NEWS, CATEGORY_TECHNICAL]:
            result["category"] = CATEGORY_TECHNICAL
        
        valid_tags = [t for t in result.get("tags", []) if t in TAGS]
        result["tags"] = valid_tags[:3]
        
        if not result.get("summary") or len(result.get("summary", "")) < 20:
            result["summary"] = f"Обнаружены изменения на сайте {competitor_name}."
            result["is_meaningful"] = False
        
        return result
        
    except json.JSONDecodeError:
        return {
            "category": CATEGORY_TECHNICAL,
            "tags": [],
            "summary": response[:500] if len(response) > 20 else f"Обнаружены изменения на сайте {competitor_name}.",
            "is_meaningful": len(response) > 50
        }


print("✅ Функции работы с LLM загружены")

# ============================================================================
# ЧАСТЬ 7: Генерация PDF отчёта
# ============================================================================

def generate_pdf_report(
    report_date: str,
    total_checked: int,
    categorized_changes: Dict[str, List[Dict]],
    errors_by_type: Dict[str, List[Dict]]
) -> str:
    """Генерирует PDF отчёт"""
    
    filename = f"/tmp/competitor_report_{report_date}.pdf"
    
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    font_regular = FONT_NAME
    font_bold = f"{FONT_NAME}-Bold" if FONT_NAME == 'DejaVuSans' else 'Helvetica-Bold'
    
    # Стили
    title_style = ParagraphStyle('Title', fontName=font_bold, fontSize=16, spaceAfter=8, alignment=1, textColor=colors.HexColor('#1a1a1a'))
    subtitle_style = ParagraphStyle('Subtitle', fontName=font_regular, fontSize=10, spaceAfter=12, alignment=1, textColor=colors.grey)
    section_style = ParagraphStyle('Section', fontName=font_bold, fontSize=13, spaceBefore=16, spaceAfter=8, textColor=colors.HexColor('#2c5aa0'))
    company_style = ParagraphStyle('Company', fontName=font_bold, fontSize=10, spaceBefore=10, spaceAfter=2, textColor=colors.HexColor('#333333'))
    summary_style = ParagraphStyle('Summary', fontName=font_regular, fontSize=9, spaceAfter=2, leading=12, leftIndent=10)
    tag_style = ParagraphStyle('Tags', fontName=font_regular, fontSize=8, spaceAfter=8, leftIndent=10)
    error_style = ParagraphStyle('Error', fontName=font_regular, fontSize=8, spaceAfter=2, textColor=colors.HexColor('#666666'))
    
    content = []
    
    # Заголовок
    content.append(Paragraph("Отчёт мониторинга конкурентов", title_style))
    content.append(Paragraph(f"Дата: {report_date}", subtitle_style))
    
    # Статистика
    total_changes = sum(len(items) for cat, items in categorized_changes.items() if cat != CATEGORY_UNREADABLE)
    total_errors = sum(len(items) for items in errors_by_type.values())
    
    stats_text = f"📊 Проверено: {total_checked} | ✅ Изменения: {total_changes} | ⚠️ Ошибки: {total_errors}"
    content.append(Paragraph(stats_text, subtitle_style))
    content.append(Spacer(1, 10))
    
    # Секции по категориям
    sections = [
        (CATEGORY_PRODUCTS, "🏷️ ПРОДУКТЫ И УСЛУГИ"),
        (CATEGORY_PRICES, "💰 ЦЕНЫ И АКЦИИ"),
        (CATEGORY_NEWS, "📰 НОВОСТИ"),
    ]
    
    for category, title in sections:
        if categorized_changes.get(category):
            content.append(Paragraph(title, section_style))
            for i, item in enumerate(categorized_changes[category], 1):
                name = item.get('competitor', 'Неизвестно')
                url = item.get('url', '')
                summary = item.get('summary', '')
                tags = item.get('tags', [])
                
                if url:
                    company_text = f"{i}. <b>{name}</b> — <a href='{url}' color='blue'>{url}</a>"
                else:
                    company_text = f"{i}. <b>{name}</b>"
                content.append(Paragraph(company_text, company_style))
                content.append(Paragraph(summary, summary_style))
                
                if tags:
                    tag_parts = [f"<font color='{TAGS.get(tag, {}).get('color', '#9E9E9E')}'><b>#{tag}</b></font>" for tag in tags]
                    content.append(Paragraph(" ".join(tag_parts), tag_style))
    
    # Технические (кратко)
    if categorized_changes.get(CATEGORY_TECHNICAL):
        content.append(Paragraph("🔧 ТЕХНИЧЕСКИЕ ИЗМЕНЕНИЯ", section_style))
        for item in categorized_changes[CATEGORY_TECHNICAL]:
            name = item.get('competitor', 'Неизвестно')
            url = item.get('url', '')
            summary = item.get('summary', '')[:100]
            text = f"• <b>{name}</b> — <a href='{url}' color='blue'>{url}</a>: {summary}" if url else f"• <b>{name}</b>: {summary}"
            content.append(Paragraph(text, error_style))
    
    # Нечитаемый контент
    if categorized_changes.get(CATEGORY_UNREADABLE):
        content.append(Paragraph("❓ НЕ УДАЛОСЬ ПРОЧИТАТЬ КОНТЕНТ", section_style))
        for item in categorized_changes[CATEGORY_UNREADABLE]:
            name = item.get('competitor', 'Неизвестно')
            url = item.get('url', '')
            text = f"• <b>{name}</b> — <a href='{url}' color='blue'>{url}</a>" if url else f"• <b>{name}</b>"
            content.append(Paragraph(text, error_style))
    
    # Ошибки
    if any(errors_by_type.values()):
        content.append(Paragraph("⚠️ НЕ УДАЛОСЬ ПРОВЕРИТЬ", section_style))
        
        error_labels = {
            "cloudflare": "🛡️ Защита Cloudflare",
            "недоступен": "🔌 Сайт недоступен",
            "таймаут": "⏱️ Таймаут",
            "другое": "❓ Другие ошибки"
        }
        
        for error_type, label in error_labels.items():
            if errors_by_type.get(error_type):
                names = [f"<a href='{item.get('url', '')}' color='blue'>{item.get('competitor', '')}</a>" 
                        if item.get('url') else item.get('competitor', '') 
                        for item in errors_by_type[error_type]]
                content.append(Paragraph(f"{label}: {', '.join(names)}", error_style))
    
    doc.build(content)
    print(f"✅ PDF создан: {filename}")
    
    return filename


print("✅ Функции генерации PDF загружены")

# ============================================================================
# ЧАСТЬ 8: Функции работы с Supabase
# ============================================================================

def get_previous_hash(competitor_id: str) -> Optional[str]:
    """Получает предыдущий хеш"""
    try:
        competitor = supabase.table('competitors').select('last_scan_id').eq('id', competitor_id).single().execute()
        if not competitor.data or not competitor.data.get('last_scan_id'):
            return None
        
        last_scan_id = competitor.data['last_scan_id']
        scan_result = supabase.table('scan_results').select('last_hash').eq('id', last_scan_id).single().execute()
        
        if scan_result.data:
            last_hash = scan_result.data.get('last_hash')
            if last_hash in ["PROTECTION_PAGE", "UNREADABLE_CONTENT", "ERROR"]:
                return None
            return last_hash
        return None
    except Exception as e:
        return None


def create_scan_result(scan_id: str, scan_date: str, competitor_id: str, new_hash: str,
                       content_changed: bool, raw_content: str = "", llm_summary: str = "",
                       report_id: str = None) -> Optional[str]:
    """Создает запись сканирования"""
    try:
        data = {
            'scan_id': scan_id,
            'scan_date': scan_date,
            'competitor_id': competitor_id,
            'last_hash': new_hash,
            'content_changed': content_changed,
            'raw_change_data': raw_content[:50000] if raw_content else None,
            'llm_summary': llm_summary if llm_summary else None,
            'report_id': report_id
        }
        result = supabase.table('scan_results').insert(data).execute()
        return result.data[0]['id'] if result.data else None
    except Exception as e:
        print(f"❌ Ошибка записи: {str(e)[:100]}")
        return None


def update_competitor_last_scan(competitor_id: str, scan_result_id: str) -> bool:
    """Обновляет last_scan_id"""
    try:
        supabase.table('competitors').update({'last_scan_id': scan_result_id}).eq('id', competitor_id).execute()
        return True
    except:
        return False


def create_summary_report(report_id: str, report_date: str) -> Optional[str]:
    """Создает запись отчёта"""
    try:
        data = {'report_id': report_id, 'report_date': report_date, 'overall_llm_report': "Генерация..."}
        result = supabase.table('summary_reports').insert(data).execute()
        return result.data[0]['id'] if result.data else None
    except:
        return None


def update_summary_report(report_id: str, overall_report: str) -> bool:
    """Обновляет отчёт"""
    try:
        supabase.table('summary_reports').update({'overall_llm_report': overall_report}).eq('id', report_id).execute()
        return True
    except:
        return False


print("✅ Функции Supabase загружены")

# ============================================================================
# ЧАСТЬ 9: Асинхронное сканирование конкурента
# ============================================================================

async def scan_competitor_async(
    competitor: Dict,
    report_id: str,
    scan_date: str,
    http_session: aiohttp.ClientSession,
    browser_context
) -> Optional[Dict[str, Any]]:
    """Асинхронное сканирование одного конкурента"""
    
    competitor_id = competitor['id']
    competitor_name = competitor.get('name', 'Unknown')
    competitor_url = competitor.get('url', '')

    print(f"🔍 {competitor_name}")

    previous_hash = get_previous_hash(competitor_id)

    # Загружаем контент
    current_content, error_type = await fetch_website_content_async(competitor_url, http_session, browser_context)

    # Обработка ошибок
    if not current_content:
        return {
            'competitor': competitor_name,
            'url': competitor_url,
            'error_type': error_type or 'недоступен',
            'is_error': True
        }

    # Проверка защиты
    if is_protection_page(current_content):
        scan_id = generate_unique_id("scan_")
        create_scan_result(scan_id, scan_date, competitor_id, "PROTECTION_PAGE", False, "", "Защита Cloudflare", None)
        return {
            'competitor': competitor_name,
            'url': competitor_url,
            'error_type': 'cloudflare',
            'is_error': True
        }

    # Проверка читаемости
    if is_unreadable_content(current_content):
        scan_id = generate_unique_id("scan_")
        create_scan_result(scan_id, scan_date, competitor_id, "UNREADABLE_CONTENT", False, "", "Нечитаемый контент", None)
        return {
            'competitor': competitor_name,
            'url': competitor_url,
            'category': CATEGORY_UNREADABLE,
            'summary': 'Контент не удалось прочитать',
            'tags': [],
            'is_error': False,
            'is_unreadable': True
        }

    # Хеш
    normalized_content = normalize_content_for_hash(current_content)
    new_hash = calculate_hash(normalized_content)

    content_changed = (previous_hash is not None) and (new_hash != previous_hash)

    scan_id = generate_unique_id("scan_")
    result_dict = None

    if content_changed:
        print(f"   🔔 Изменения: {competitor_name}")
        
        # Анализ через LLM
        analysis = await analyze_changes_with_category_async(competitor_name, current_content, http_session)
        
        if not analysis.get("is_meaningful", True):
            result_dict = {
                'competitor': competitor_name,
                'url': competitor_url,
                'category': CATEGORY_UNREADABLE,
                'summary': 'Контент изменился, но не информативен',
                'tags': [],
                'is_error': False,
                'is_unreadable': True
            }
        else:
            result_dict = {
                'competitor': competitor_name,
                'url': competitor_url,
                'category': analysis['category'],
                'summary': analysis['summary'],
                'tags': analysis['tags'],
                'is_error': False,
                'is_unreadable': False
            }
        
        llm_summary = analysis.get('summary', '')
    else:
        llm_summary = ""

    # Сохраняем
    scan_result_id = create_scan_result(
        scan_id, scan_date, competitor_id, new_hash, content_changed,
        current_content if content_changed else "", llm_summary,
        report_id if content_changed else None
    )

    if scan_result_id:
        update_competitor_last_scan(competitor_id, scan_result_id)

    return result_dict


print("✅ Асинхронное сканирование загружено")

# ============================================================================
# ЧАСТЬ 10: Главная функция с параллельным выполнением
# ============================================================================

async def run_monitoring_async():
    """Асинхронный мониторинг с параллельным выполнением"""
    
    print("🚀 Запуск параллельного мониторинга...")
    start_time = time.time()
    
    init_semaphores()
    
    send_telegram_message("🚀 <b>Запуск мониторинга конкурентов</b>")

    current_date = datetime.now().strftime("%Y-%m-%d")
    report_id = generate_unique_id("report_")
    summary_report_id = create_summary_report(report_id, current_date)

    if not summary_report_id:
        send_telegram_message("❌ <b>Ошибка:</b> Не удалось создать отчет")
        return

    # Получаем конкурентов
    try:
        competitors_response = supabase.table('competitors').select('*').execute()
        competitors = competitors_response.data
    except Exception as e:
        send_telegram_message(f"❌ <b>Ошибка:</b> {str(e)[:200]}")
        return

    total_competitors = len(competitors)
    print(f"🌐 Конкурентов: {total_competitors}")

    # Результаты
    categorized_changes = {
        CATEGORY_PRODUCTS: [], CATEGORY_PRICES: [], CATEGORY_NEWS: [],
        CATEGORY_TECHNICAL: [], CATEGORY_UNREADABLE: []
    }
    errors_by_type = {"cloudflare": [], "недоступен": [], "таймаут": [], "другое": []}

    # Создаём HTTP сессию и браузер
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, ssl=False)
    
    async with aiohttp.ClientSession(connector=connector) as http_session:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            browser_context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )
            
            # Создаём задачи для всех конкурентов
            tasks = [
                scan_competitor_async(competitor, summary_report_id, current_date, http_session, browser_context)
                for competitor in competitors
            ]
            
            # Выполняем параллельно
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            await browser_context.close()
            await browser.close()

    # Обрабатываем результаты
    for result in results:
        if isinstance(result, Exception):
            continue
        if not result:
            continue
            
        if result.get('is_error'):
            error_type = result.get('error_type', 'другое')
            if 'cloudflare' in error_type.lower():
                errors_by_type["cloudflare"].append(result)
            elif error_type in ['нет_соединения', 'недоступен', 'страница_не_найдена', 'ошибка_сервера']:
                errors_by_type["недоступен"].append(result)
            elif 'таймаут' in error_type:
                errors_by_type["таймаут"].append(result)
            else:
                errors_by_type["другое"].append(result)
        elif result.get('is_unreadable'):
            categorized_changes[CATEGORY_UNREADABLE].append(result)
        else:
            category = result.get('category', CATEGORY_TECHNICAL)
            if category in categorized_changes:
                categorized_changes[category].append(result)
            else:
                categorized_changes[CATEGORY_TECHNICAL].append(result)

    # Время выполнения
    elapsed_time = time.time() - start_time
    print(f"⏱️ Время выполнения: {elapsed_time:.1f} сек")

    # Обновляем отчёт
    total_changes = sum(len(items) for cat, items in categorized_changes.items() if cat != CATEGORY_UNREADABLE)
    summary_text = f"Изменения: {total_changes}"
    update_summary_report(summary_report_id, summary_text)

    # Генерируем PDF
    print("📄 Генерация PDF...")
    pdf_path = generate_pdf_report(current_date, total_competitors, categorized_changes, errors_by_type)

    # Telegram
    total_errors = sum(len(items) for items in errors_by_type.values())
    unreadable_count = len(categorized_changes[CATEGORY_UNREADABLE])
    
    telegram_message = f"""📊 <b>Мониторинг завершён</b>

📅 Дата: {current_date}
⏱️ Время: {elapsed_time:.0f} сек
🌐 Проверено: <b>{total_competitors}</b>

✅ <b>Изменения: {total_changes}</b>
   🏷️ Продукты: {len(categorized_changes[CATEGORY_PRODUCTS])}
   💰 Цены/акции: {len(categorized_changes[CATEGORY_PRICES])}
   📰 Новости: {len(categorized_changes[CATEGORY_NEWS])}
   🔧 Технические: {len(categorized_changes[CATEGORY_TECHNICAL])}

⚠️ <b>Проблемы: {total_errors + unreadable_count}</b>
   🛡️ Cloudflare: {len(errors_by_type['cloudflare'])}
   🔌 Недоступны: {len(errors_by_type['недоступен'])}
   ❓ Нечитаемые: {unreadable_count}

📎 Подробный отчёт во вложении"""

    send_telegram_document(pdf_path, telegram_message)
    
    try:
        os.remove(pdf_path)
    except:
        pass

    print("✅ Мониторинг завершён")


def run_monitoring_system():
    """Точка входа - запуск асинхронного мониторинга"""
    asyncio.run(run_monitoring_async())


print("✅ Главная функция загружена")

# ============================================================================
# ЧАСТЬ 11: ЗАПУСК
# ============================================================================

if __name__ == "__main__":
    run_monitoring_system()
