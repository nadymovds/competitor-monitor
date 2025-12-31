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
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from supabase import create_client, Client
from bs4 import BeautifulSoup
import time
import asyncio
import nest_asyncio

# Импорты для Playwright
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Импорты для PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Применяем nest_asyncio для поддержки вложенных event loop'ов
nest_asyncio.apply()

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
REQUEST_TIMEOUT = 45  # Увеличен таймаут
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MIN_CONTENT_LENGTH = 300
PLAYWRIGHT_TIMEOUT = 45000  # Увеличен таймаут
MAX_RETRIES = 4  # Увеличено количество попыток

# --- Категории изменений ---
CATEGORY_PRODUCTS = "products"      # Продукты и услуги
CATEGORY_PRICES = "prices"          # Цены и акции
CATEGORY_NEWS = "news"              # Новости
CATEGORY_TECHNICAL = "technical"    # Технические изменения
CATEGORY_UNREADABLE = "unreadable"  # Нечитаемый контент

# --- Теги ---
TAGS = {
    "новый_продукт": {"color": "#4CAF50", "text": "белый"},
    "оборудование": {"color": "#2196F3", "text": "белый"},
    "тахографы": {"color": "#9C27B0", "text": "белый"},
    "мониторинг": {"color": "#00BCD4", "text": "белый"},
    "ПО": {"color": "#607D8B", "text": "белый"},
    "акция": {"color": "#FF9800", "text": "белый"},
    "скидка": {"color": "#F44336", "text": "белый"},
    "новая_цена": {"color": "#E91E63", "text": "белый"},
    "бесплатно": {"color": "#8BC34A", "text": "белый"},
    "новость": {"color": "#3F51B5", "text": "белый"},
    "важное": {"color": "#f44336", "text": "белый"},
    "партнёрство": {"color": "#009688", "text": "белый"},
    "законодательство": {"color": "#795548", "text": "белый"},
    "обновление_сайта": {"color": "#9E9E9E", "text": "белый"},
    "wialon": {"color": "#FF5722", "text": "белый"},
    "глонасс": {"color": "#673AB7", "text": "белый"},
}

# Инициализация Supabase клиента
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    # Убираем даты в разных форматах
    content = re.sub(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', '', content)
    content = re.sub(r'\d{4}-\d{2}-\d{2}', '', content)
    
    # Убираем время
    content = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', '', content)
    
    # Убираем года
    content = re.sub(r'202[0-9]|203[0-9]', '', content)
    
    # Убираем счётчики посетителей и подобное
    content = re.sub(r'посетител\w*\s*:?\s*\d+', '', content, flags=re.IGNORECASE)
    content = re.sub(r'онлайн\s*:?\s*\d+', '', content, flags=re.IGNORECASE)
    content = re.sub(r'просмотр\w*\s*:?\s*\d+', '', content, flags=re.IGNORECASE)
    
    # Убираем множественные пробелы
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
    """Проверяет, является ли контент страницей защиты (Cloudflare, Captcha и т.п.)"""
    protection_patterns = [
        'cloudflare',
        'ray id',
        'checking your browser',
        'ddos protection',
        'please wait while we verify',
        'just a moment',
        'enable javascript and cookies',
        'attention required',
        'security check',
        'access denied',
        'please complete the security check',
        'recaptcha',
        'hcaptcha',
        'verifying you are human',
        'browser verification',
        'защита от ботов',
        'проверка браузера',
        'подождите, идет проверка',
    ]
    
    content_lower = content.lower()
    
    for pattern in protection_patterns:
        if pattern in content_lower:
            return True
    
    if len(content) < 1000:
        short_content_patterns = ['checking', 'verify', 'moment', 'wait']
        matches = sum(1 for p in short_content_patterns if p in content_lower)
        if matches >= 2:
            return True
    
    return False


def is_unreadable_content(content: str) -> bool:
    """Проверяет, является ли контент нечитаемым (бинарные данные, кодировка)"""
    if not content or len(content) < 100:
        return True
    
    # Проверяем на бинарные/нечитаемые символы
    non_printable = sum(1 for c in content[:1000] if ord(c) > 127 and not c.isalpha())
    if non_printable > len(content[:1000]) * 0.3:
        return True
    
    # Проверяем на наличие осмысленных слов
    russian_words = len(re.findall(r'[а-яА-ЯёЁ]{3,}', content[:2000]))
    english_words = len(re.findall(r'[a-zA-Z]{3,}', content[:2000]))
    
    if russian_words + english_words < 20:
        return True
    
    # Проверяем на характерные признаки сжатого/бинарного контента
    binary_patterns = [
        r'[\x00-\x08\x0b\x0c\x0e-\x1f]',  # Контрольные символы
        r'�{3,}',  # Множественные символы замены
    ]
    
    for pattern in binary_patterns:
        if re.search(pattern, content[:1000]):
            return True
    
    return False


async def render_page_with_browser(url: str, timeout: int = PLAYWRIGHT_TIMEOUT) -> Optional[str]:
    """Загружает страницу через безголовый браузер Playwright"""
    try:
        print(f"   🌐 Запуск браузерного рендеринга...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True,
                java_script_enabled=True
            )

            page = await context.new_page()
            
            # Блокируем ненужные ресурсы для ускорения
            await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())

            try:
                await page.goto(url, timeout=timeout, wait_until='networkidle')
                
                # Ждём дополнительно для SPA
                await page.wait_for_timeout(2000)
                
                html_content = await page.content()
                soup = BeautifulSoup(html_content, 'lxml')
                text = clean_html_content(soup)

                print(f"   ✅ Браузерный рендеринг успешен: {len(text)} символов")

                await context.close()
                await browser.close()
                return text

            except PlaywrightTimeout:
                print(f"   ⚠️ Таймаут при загрузке через браузер")
                await context.close()
                await browser.close()
                return None
            except Exception as e:
                print(f"   ⚠️ Ошибка внутри Playwright: {str(e)[:200]}")
                await context.close()
                await browser.close()
                return None

    except Exception as e:
        print(f"   ⚠️ Ошибка браузерного рендеринга: {str(e)[:200]}")
        return None


def is_content_insufficient(content: str) -> bool:
    """Проверяет, достаточно ли контента или нужен fallback"""
    if len(content) < MIN_CONTENT_LENGTH:
        return True

    spa_patterns = [
        '<div id="root"></div>',
        '<div id="app"></div>',
        'document.getElementById',
        'window.__INITIAL_STATE__'
    ]

    if len(content) < 500:
        for pattern in spa_patterns:
            if pattern.lower() in content.lower():
                return True

    return False


def fetch_website_content(url: str, retry_count: int = MAX_RETRIES) -> Tuple[Optional[str], str]:
    """
    Загружает и очищает содержимое веб-сайта с обходом защиты.
    Возвращает (контент, статус_ошибки)
    """
    last_error = ""
    
    for attempt in range(retry_count):
        try:
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
            }

            session = requests.Session()
            response = session.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                verify=False,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Пауза между попытками
            time.sleep(1 + attempt)

            # Пробуем декодировать контент
            try:
                content = response.content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = response.content.decode('cp1251')
                except:
                    content = response.text

            soup = BeautifulSoup(content, 'lxml')
            text = clean_html_content(soup)

            if is_content_insufficient(text):
                print(f"   ⚠️ Недостаточно контента ({len(text)} символов), попытка {attempt + 1}/{retry_count}")
                print(f"   ↺ Переключение на браузерный рендеринг...")

                try:
                    browser_text = asyncio.run(render_page_with_browser(url))
                except RuntimeError as e:
                    print(f"   ⚠️ Ошибка asyncio.run(): {e}")
                    browser_text = None

                if browser_text and len(browser_text) >= MIN_CONTENT_LENGTH:
                    return (browser_text, "")
                elif attempt < retry_count - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    return (text if text else None, "недостаточно_контента")

            print(f"   ✅ Обычная загрузка успешна: {len(text)} символов")
            return (text, "")

        except requests.exceptions.SSLError as e:
            last_error = "ssl_ошибка"
            print(f"   ⚠️ SSL ошибка на попытке {attempt + 1}/{retry_count}")
            if attempt < retry_count - 1:
                time.sleep(2 * (attempt + 1))
            else:
                try:
                    result = asyncio.run(render_page_with_browser(url))
                    return (result, "" if result else "ssl_ошибка")
                except RuntimeError:
                    return (None, "ssl_ошибка")

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            if status_code == 403:
                last_error = "доступ_запрещён"
                print(f"   ⚠️ 403 Forbidden на попытке {attempt + 1}/{retry_count}")
                if attempt < retry_count - 1:
                    time.sleep(3 * (attempt + 1))
                else:
                    try:
                        result = asyncio.run(render_page_with_browser(url))
                        return (result, "" if result else "доступ_запрещён")
                    except RuntimeError:
                        return (None, "доступ_запрещён")
            elif status_code == 404:
                return (None, "страница_не_найдена")
            elif status_code >= 500:
                last_error = "ошибка_сервера"
                if attempt < retry_count - 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                return (None, "ошибка_сервера")
            else:
                return (None, f"http_{status_code}")

        except requests.exceptions.ConnectTimeout:
            last_error = "таймаут_соединения"
            print(f"   ⚠️ Таймаут соединения на попытке {attempt + 1}/{retry_count}")
            if attempt < retry_count - 1:
                time.sleep(2 * (attempt + 1))
            else:
                try:
                    result = asyncio.run(render_page_with_browser(url, timeout=60000))
                    return (result, "" if result else "таймаут")
                except RuntimeError:
                    return (None, "таймаут")

        except requests.exceptions.ConnectionError:
            last_error = "нет_соединения"
            print(f"   ⚠️ Ошибка соединения на попытке {attempt + 1}/{retry_count}")
            if attempt < retry_count - 1:
                time.sleep(3 * (attempt + 1))
            else:
                return (None, "нет_соединения")

        except Exception as e:
            last_error = "неизвестная_ошибка"
            print(f"   ⚠️ Ошибка на попытке {attempt + 1}/{retry_count}: {str(e)[:200]}")
            if attempt < retry_count - 1:
                time.sleep(2 * (attempt + 1))
            else:
                try:
                    result = asyncio.run(render_page_with_browser(url))
                    return (result, "" if result else last_error)
                except RuntimeError:
                    return (None, last_error)

    return (None, last_error or "неизвестная_ошибка")


print("✅ Вспомогательные функции загружены")

# ============================================================================
# ЧАСТЬ 5: Функции работы с LLM (OpenRouter)
# ============================================================================

def call_llm(prompt: str, max_tokens: int = 500, retry_count: int = 2) -> Optional[str]:
    """Отправляет запрос к LLM через OpenRouter API с повторными попытками"""
    for attempt in range(retry_count):
        try:
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

            response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            time.sleep(2)

            result = response.json()
            answer = result['choices'][0]['message']['content'].strip()
            return answer

        except Exception as e:
            print(f"   ⚠️ Ошибка LLM (попытка {attempt + 1}/{retry_count}): {str(e)[:100]}")
            if attempt < retry_count - 1:
                time.sleep(5)
            else:
                return None
    
    return None


def analyze_changes_with_category(competitor_name: str, new_content: str) -> Dict[str, Any]:
    """Анализирует изменения и определяет категорию и теги"""
    
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
- "news" — новости компании, события, партнёрства, изменения в законодательстве, уход/приход на рынок
- "technical" — обновления сайта, исправления, технические изменения

ДОСТУПНЫЕ ТЕГИ: новый_продукт, оборудование, тахографы, мониторинг, ПО, акция, скидка, новая_цена, бесплатно, новость, важное, партнёрство, законодательство, обновление_сайта, wialon, глонасс

ВАЖНО:
- is_meaningful=false если контент нечитаемый, бессмысленный или не содержит полезной информации
- summary должен быть конкретным и информативным (3-4 предложения)
- Выбери 1-3 наиболее подходящих тега

Ответь ТОЛЬКО JSON, без пояснений."""

    response = call_llm(prompt, max_tokens=400)
    
    if not response:
        return {
            "category": CATEGORY_TECHNICAL,
            "tags": [],
            "summary": f"Обнаружены изменения на сайте {competitor_name}.",
            "is_meaningful": False
        }
    
    # Парсим JSON из ответа
    try:
        # Убираем возможные markdown-обёртки
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r'^```json?\s*', '', json_str)
            json_str = re.sub(r'\s*```$', '', json_str)
        
        result = json.loads(json_str)
        
        # Валидация категории
        if result.get("category") not in [CATEGORY_PRODUCTS, CATEGORY_PRICES, CATEGORY_NEWS, CATEGORY_TECHNICAL]:
            result["category"] = CATEGORY_TECHNICAL
        
        # Валидация тегов
        valid_tags = [t for t in result.get("tags", []) if t in TAGS]
        result["tags"] = valid_tags[:3]  # Максимум 3 тега
        
        # Проверка summary
        if not result.get("summary") or len(result.get("summary", "")) < 20:
            result["summary"] = f"Обнаружены изменения на сайте {competitor_name}."
            result["is_meaningful"] = False
        
        return result
        
    except json.JSONDecodeError:
        # Если не удалось распарсить JSON, пытаемся извлечь summary
        return {
            "category": CATEGORY_TECHNICAL,
            "tags": [],
            "summary": response[:500] if len(response) > 20 else f"Обнаружены изменения на сайте {competitor_name}.",
            "is_meaningful": len(response) > 50
        }


print("✅ Функции работы с LLM загружены")

# ============================================================================
# ЧАСТЬ 6: Генерация PDF отчёта
# ============================================================================

def generate_pdf_report(
    report_date: str,
    total_checked: int,
    categorized_changes: Dict[str, List[Dict]],
    errors_by_type: Dict[str, List[Dict]]
) -> str:
    """Генерирует PDF отчёт с категориями и кликабельными ссылками"""
    
    filename = f"/tmp/competitor_report_{report_date}.pdf"
    
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    # Шрифты
    font_regular = FONT_NAME
    font_bold = f"{FONT_NAME}-Bold" if FONT_NAME == 'DejaVuSans' else 'Helvetica-Bold'
    
    # Стили
    title_style = ParagraphStyle(
        'Title',
        fontName=font_bold,
        fontSize=16,
        spaceAfter=8,
        alignment=1,
        textColor=colors.HexColor('#1a1a1a')
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        fontName=font_regular,
        fontSize=10,
        spaceAfter=12,
        alignment=1,
        textColor=colors.grey
    )
    
    section_style = ParagraphStyle(
        'Section',
        fontName=font_bold,
        fontSize=13,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor('#2c5aa0')
    )
    
    company_style = ParagraphStyle(
        'Company',
        fontName=font_bold,
        fontSize=10,
        spaceBefore=10,
        spaceAfter=2,
        textColor=colors.HexColor('#333333')
    )
    
    summary_style = ParagraphStyle(
        'Summary',
        fontName=font_regular,
        fontSize=9,
        spaceAfter=2,
        leading=12,
        leftIndent=10
    )
    
    tag_style = ParagraphStyle(
        'Tags',
        fontName=font_regular,
        fontSize=8,
        spaceAfter=8,
        leftIndent=10
    )
    
    error_style = ParagraphStyle(
        'Error',
        fontName=font_regular,
        fontSize=8,
        spaceAfter=2,
        textColor=colors.HexColor('#666666')
    )
    
    # Контент
    content = []
    
    # Заголовок
    content.append(Paragraph("Отчёт мониторинга конкурентов", title_style))
    content.append(Paragraph(f"Дата: {report_date}", subtitle_style))
    
    # Статистика
    total_changes = sum(len(items) for items in categorized_changes.values())
    total_errors = sum(len(items) for items in errors_by_type.values())
    
    stats_text = f"📊 Проверено: {total_checked} | ✅ Изменения: {total_changes} | ⚠️ Ошибки: {total_errors}"
    content.append(Paragraph(stats_text, subtitle_style))
    content.append(Spacer(1, 10))
    
    # Секция: Продукты и услуги
    if categorized_changes.get(CATEGORY_PRODUCTS):
        content.append(Paragraph("🏷️ ПРОДУКТЫ И УСЛУГИ", section_style))
        for i, item in enumerate(categorized_changes[CATEGORY_PRODUCTS], 1):
            content.extend(format_change_item(i, item, company_style, summary_style, tag_style, font_regular))
    
    # Секция: Цены и акции
    if categorized_changes.get(CATEGORY_PRICES):
        content.append(Paragraph("💰 ЦЕНЫ И АКЦИИ", section_style))
        for i, item in enumerate(categorized_changes[CATEGORY_PRICES], 1):
            content.extend(format_change_item(i, item, company_style, summary_style, tag_style, font_regular))
    
    # Секция: Новости
    if categorized_changes.get(CATEGORY_NEWS):
        content.append(Paragraph("📰 НОВОСТИ", section_style))
        for i, item in enumerate(categorized_changes[CATEGORY_NEWS], 1):
            content.extend(format_change_item(i, item, company_style, summary_style, tag_style, font_regular))
    
    # Секция: Технические (кратко)
    if categorized_changes.get(CATEGORY_TECHNICAL):
        content.append(Paragraph("🔧 ТЕХНИЧЕСКИЕ ИЗМЕНЕНИЯ", section_style))
        for item in categorized_changes[CATEGORY_TECHNICAL]:
            name = item.get('competitor', 'Неизвестно')
            url = item.get('url', '')
            summary = item.get('summary', '')[:100]
            
            if url:
                text = f"• <b>{name}</b> — <a href='{url}' color='blue'>{url}</a>: {summary}"
            else:
                text = f"• <b>{name}</b>: {summary}"
            content.append(Paragraph(text, error_style))
    
    # Секция: Нечитаемый контент
    if categorized_changes.get(CATEGORY_UNREADABLE):
        content.append(Paragraph("❓ НЕ УДАЛОСЬ ПРОЧИТАТЬ КОНТЕНТ", section_style))
        for item in categorized_changes[CATEGORY_UNREADABLE]:
            name = item.get('competitor', 'Неизвестно')
            url = item.get('url', '')
            if url:
                text = f"• <b>{name}</b> — <a href='{url}' color='blue'>{url}</a>"
            else:
                text = f"• <b>{name}</b>"
            content.append(Paragraph(text, error_style))
    
    # Секция: Ошибки по типам
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
                items = errors_by_type[error_type]
                names_with_links = []
                for item in items:
                    name = item.get('competitor', '')
                    url = item.get('url', '')
                    if url:
                        names_with_links.append(f"<a href='{url}' color='blue'>{name}</a>")
                    else:
                        names_with_links.append(name)
                
                text = f"{label}: {', '.join(names_with_links)}"
                content.append(Paragraph(text, error_style))
    
    # Генерация PDF
    doc.build(content)
    print(f"✅ PDF отчёт создан: {filename}")
    
    return filename


def format_change_item(index: int, item: Dict, company_style, summary_style, tag_style, font_regular) -> List:
    """Форматирует один элемент изменения для PDF"""
    elements = []
    
    name = item.get('competitor', 'Неизвестно')
    url = item.get('url', '')
    summary = item.get('summary', '')
    tags = item.get('tags', [])
    
    # Название компании с ссылкой
    if url:
        company_text = f"{index}. <b>{name}</b> — <a href='{url}' color='blue'>{url}</a>"
    else:
        company_text = f"{index}. <b>{name}</b>"
    elements.append(Paragraph(company_text, company_style))
    
    # Описание
    elements.append(Paragraph(summary, summary_style))
    
    # Теги с цветами
    if tags:
        tag_parts = []
        for tag in tags:
            tag_info = TAGS.get(tag, {"color": "#9E9E9E"})
            color = tag_info["color"]
            tag_parts.append(f"<font color='{color}'><b>#{tag}</b></font>")
        elements.append(Paragraph(" ".join(tag_parts), tag_style))
    
    return elements


print("✅ Функции генерации PDF загружены")

# ============================================================================
# ЧАСТЬ 7: Функции работы с Supabase
# ============================================================================

def get_previous_hash(competitor_id: str) -> Optional[str]:
    """Получает предыдущий хеш из последней записи сканирования"""
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
        print(f"⚠️ Не удалось получить предыдущий хеш: {str(e)}")
        return None


def create_scan_result(
    scan_id: str,
    scan_date: str,
    competitor_id: str,
    new_hash: str,
    content_changed: bool,
    raw_content: str = "",
    llm_summary: str = "",
    report_id: str = None
) -> Optional[str]:
    """Создает новую запись в таблице scan_results"""
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

        if result.data and len(result.data) > 0:
            return result.data[0]['id']
        return None

    except Exception as e:
        print(f"❌ Ошибка при создании записи scan_results: {str(e)}")
        return None


def update_competitor_last_scan(competitor_id: str, scan_result_id: str) -> bool:
    """Обновляет ссылку на последнее сканирование в записи конкурента"""
    try:
        supabase.table('competitors').update({
            'last_scan_id': scan_result_id
        }).eq('id', competitor_id).execute()
        return True
    except Exception as e:
        print(f"❌ Ошибка при обновлении last_scan_id: {str(e)}")
        return False


def create_summary_report(report_id: str, report_date: str) -> Optional[str]:
    """Создает новую запись в таблице summary_reports"""
    try:
        data = {
            'report_id': report_id,
            'report_date': report_date,
            'overall_llm_report': "Генерация отчета..."
        }

        result = supabase.table('summary_reports').insert(data).execute()

        if result.data and len(result.data) > 0:
            return result.data[0]['id']
        return None

    except Exception as e:
        print(f"❌ Ошибка при создании summary_reports: {str(e)}")
        return None


def update_summary_report(report_id: str, overall_report: str) -> bool:
    """Обновляет общий отчет в таблице summary_reports"""
    try:
        supabase.table('summary_reports').update({
            'overall_llm_report': overall_report
        }).eq('id', report_id).execute()
        return True
    except Exception as e:
        print(f"❌ Ошибка при обновлении overall_llm_report: {str(e)}")
        return False


print("✅ Функции работы с Supabase загружены")

# ============================================================================
# ЧАСТЬ 8: Основная логика мониторинга
# ============================================================================

def scan_competitor(
    competitor: Dict,
    report_id: str,
    scan_date: str
) -> Optional[Dict[str, Any]]:
    """Сканирует одного конкурента и создает запись в scan_results"""
    competitor_id = competitor['id']
    competitor_name = competitor.get('name', 'Unknown')
    competitor_url = competitor.get('url', '')

    print(f"\n🔍 Сканирование: {competitor_name}")
    print(f"   URL: {competitor_url}")

    previous_hash = get_previous_hash(competitor_id)

    if previous_hash:
        print(f"   🔑 Предыдущий хеш: {previous_hash[:16]}...")
    else:
        print(f"   🆕 Первое сканирование")

    # Загружаем контент
    current_content, error_type = fetch_website_content(competitor_url)

    # Обработка ошибок загрузки
    if not current_content:
        print(f"   ❌ Не удалось загрузить: {error_type}")
        return {
            'competitor': competitor_name,
            'url': competitor_url,
            'error_type': error_type or 'недоступен',
            'is_error': True
        }

    # Проверка на страницу защиты
    if is_protection_page(current_content):
        print(f"   ⚠️ Страница защиты (Cloudflare/Captcha)")
        
        scan_id = generate_unique_id("scan_")
        create_scan_result(
            scan_id=scan_id,
            scan_date=scan_date,
            competitor_id=competitor_id,
            new_hash="PROTECTION_PAGE",
            content_changed=False,
            raw_content="",
            llm_summary="Защита Cloudflare/Captcha",
            report_id=None
        )
        
        return {
            'competitor': competitor_name,
            'url': competitor_url,
            'error_type': 'cloudflare',
            'is_error': True
        }

    # Проверка на нечитаемый контент
    if is_unreadable_content(current_content):
        print(f"   ⚠️ Нечитаемый контент")
        
        scan_id = generate_unique_id("scan_")
        create_scan_result(
            scan_id=scan_id,
            scan_date=scan_date,
            competitor_id=competitor_id,
            new_hash="UNREADABLE_CONTENT",
            content_changed=False,
            raw_content="",
            llm_summary="Нечитаемый контент",
            report_id=None
        )
        
        return {
            'competitor': competitor_name,
            'url': competitor_url,
            'category': CATEGORY_UNREADABLE,
            'summary': 'Контент сайта не удалось прочитать (возможно, бинарные данные или проблема с кодировкой)',
            'tags': [],
            'is_error': False,
            'is_unreadable': True
        }

    # Нормализуем контент и считаем хеш
    normalized_content = normalize_content_for_hash(current_content)
    new_hash = calculate_hash(normalized_content)
    print(f"   ✅ Хеш: {new_hash[:16]}...")

    content_changed = (previous_hash is not None) and (new_hash != previous_hash)

    scan_id = generate_unique_id("scan_")
    result_dict = None

    if content_changed:
        print(f"   🔔 ИЗМЕНЕНИЯ ОБНАРУЖЕНЫ!")
        print(f"   🤖 Анализ через LLM...")
        
        # Анализируем с категоризацией
        analysis = analyze_changes_with_category(competitor_name, current_content)
        
        if not analysis.get("is_meaningful", True):
            # Если LLM считает контент бессмысленным
            print(f"   ⚠️ LLM: контент не информативен")
            result_dict = {
                'competitor': competitor_name,
                'url': competitor_url,
                'category': CATEGORY_UNREADABLE,
                'summary': 'Контент изменился, но не содержит полезной информации',
                'tags': [],
                'is_error': False,
                'is_unreadable': True
            }
        else:
            print(f"   📄 Категория: {analysis['category']}")
            print(f"   🏷️ Теги: {analysis['tags']}")
            
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
        print(f"   ✅ Изменений нет")
        llm_summary = ""

    # Сохраняем результат
    scan_result_id = create_scan_result(
        scan_id=scan_id,
        scan_date=scan_date,
        competitor_id=competitor_id,
        new_hash=new_hash,
        content_changed=content_changed,
        raw_content=current_content if content_changed else "",
        llm_summary=llm_summary,
        report_id=report_id if content_changed else None
    )

    if scan_result_id:
        print(f"   💾 Сохранено: {scan_id}")
        update_competitor_last_scan(competitor_id, scan_result_id)

    return result_dict


print("✅ Основная логика мониторинга загружена")

# ============================================================================
# ЧАСТЬ 9: Функция для запуска системы мониторинга
# ============================================================================

def run_monitoring_system():
    """Запускает систему мониторинга конкурентов"""
    print("🚀 Запуск системы мониторинга конкурентов...")
    
    send_telegram_message("🚀 <b>Запуск мониторинга конкурентов</b>")

    current_date = datetime.now().strftime("%Y-%m-%d")
    report_id = generate_unique_id("report_")
    summary_report_id = create_summary_report(report_id, current_date)

    if not summary_report_id:
        print("❌ Не удалось создать отчет")
        send_telegram_message("❌ <b>Ошибка:</b> Не удалось создать отчет")
        return

    print(f"📊 Отчет: {report_id}")

    # Получаем конкурентов
    try:
        competitors_response = supabase.table('competitors').select('*').execute()
        competitors = competitors_response.data
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        send_telegram_message(f"❌ <b>Ошибка:</b> {str(e)[:200]}")
        return

    total_competitors = len(competitors)
    print(f"🌐 Конкурентов: {total_competitors}")

    # Структуры для сбора результатов
    categorized_changes = {
        CATEGORY_PRODUCTS: [],
        CATEGORY_PRICES: [],
        CATEGORY_NEWS: [],
        CATEGORY_TECHNICAL: [],
        CATEGORY_UNREADABLE: []
    }
    
    errors_by_type = {
        "cloudflare": [],
        "недоступен": [],
        "таймаут": [],
        "другое": []
    }

    # Сканируем
    for competitor in competitors:
        result = scan_competitor(competitor, summary_report_id, current_date)
        
        if result:
            if result.get('is_error'):
                # Классифицируем ошибку
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
                # Добавляем в соответствующую категорию
                category = result.get('category', CATEGORY_TECHNICAL)
                if category in categorized_changes:
                    categorized_changes[category].append(result)
                else:
                    categorized_changes[CATEGORY_TECHNICAL].append(result)
        
        time.sleep(2)

    # Обновляем отчёт в Supabase
    total_changes = sum(len(items) for cat, items in categorized_changes.items() if cat != CATEGORY_UNREADABLE)
    summary_text = f"Изменения: {total_changes} (продукты: {len(categorized_changes[CATEGORY_PRODUCTS])}, цены: {len(categorized_changes[CATEGORY_PRICES])}, новости: {len(categorized_changes[CATEGORY_NEWS])})"
    update_summary_report(summary_report_id, summary_text)

    # Генерируем PDF
    print("📄 Генерация PDF...")
    pdf_path = generate_pdf_report(
        report_date=current_date,
        total_checked=total_competitors,
        categorized_changes=categorized_changes,
        errors_by_type=errors_by_type
    )

    # Статистика для Telegram
    total_changes = sum(len(items) for cat, items in categorized_changes.items() if cat != CATEGORY_UNREADABLE)
    total_errors = sum(len(items) for items in errors_by_type.values())
    unreadable_count = len(categorized_changes[CATEGORY_UNREADABLE])
    
    telegram_message = f"""📊 <b>Мониторинг завершён</b>

📅 Дата: {current_date}
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
    
    # Удаляем временный файл
    try:
        os.remove(pdf_path)
    except:
        pass

    print("✅ Мониторинг завершён")


print("✅ Функция run_monitoring_system загружена")

# ============================================================================
# ЧАСТЬ 10: ЗАПУСК СИСТЕМЫ
# ============================================================================

if __name__ == "__main__":
    run_monitoring_system()
