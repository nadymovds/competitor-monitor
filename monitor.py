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
from datetime import datetime
from typing import Optional, List, Dict, Any
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
REQUEST_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MIN_CONTENT_LENGTH = 300
PLAYWRIGHT_TIMEOUT = 30000

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
    
    # Fallback - используем Helvetica
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


def clean_html_content(soup: BeautifulSoup) -> str:
    """Очищает HTML от скриптов, стилей и служебных элементов"""
    for element in soup(['script', 'style', 'nav', 'footer', 'header']):
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
    
    # Проверяем паттерны
    for pattern in protection_patterns:
        if pattern in content_lower:
            return True
    
    # Дополнительная проверка: слишком короткий контент с признаками защиты
    if len(content) < 1000:
        short_content_patterns = [
            'checking',
            'verify',
            'moment',
            'wait',
        ]
        matches = sum(1 for p in short_content_patterns if p in content_lower)
        if matches >= 2:
            return True
    
    return False


async def render_page_with_browser(url: str) -> Optional[str]:
    """Загружает страницу через безголовый браузер Playwright"""
    try:
        print(f"   🌐 Запуск браузерного рендеринга...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )

            page = await context.new_page()

            try:
                await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until='networkidle')
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


def fetch_website_content(url: str, retry_count: int = 3) -> Optional[str]:
    """Загружает и очищает содержимое веб-сайта с обходом защиты"""
    for attempt in range(retry_count):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
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
            time.sleep(1)

            soup = BeautifulSoup(response.content, 'lxml')
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
                    return browser_text
                elif attempt < retry_count - 1:
                    time.sleep(2)
                    continue
                else:
                    print(f"   ⚠️ Даже браузерный рендеринг не дал достаточно контента")
                    return text if text else None

            print(f"   ✅ Обычная загрузка успешна: {len(text)} символов")
            return text

        except requests.exceptions.SSLError as e:
            print(f"   ⚠️ SSL ошибка на попытке {attempt + 1}/{retry_count}")
            if attempt < retry_count - 1:
                time.sleep(2)
            else:
                try:
                    return asyncio.run(render_page_with_browser(url))
                except RuntimeError:
                    return None

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"   ⚠️ 403 Forbidden на попытке {attempt + 1}/{retry_count}")
                if attempt < retry_count - 1:
                    time.sleep(3 * (attempt + 1))
                else:
                    try:
                        return asyncio.run(render_page_with_browser(url))
                    except RuntimeError:
                        return None
            else:
                print(f"   ❌ HTTP ошибка: {str(e)}")
                return None

        except Exception as e:
            print(f"   ⚠️ Ошибка на попытке {attempt + 1}/{retry_count}: {str(e)[:200]}")
            if attempt < retry_count - 1:
                time.sleep(2)
            else:
                try:
                    return asyncio.run(render_page_with_browser(url))
                except RuntimeError:
                    return None

    return None


print("✅ Вспомогательные функции загружены")

# ============================================================================
# ЧАСТЬ 5: Функции работы с LLM (OpenRouter)
# ============================================================================

def call_llm(prompt: str, max_tokens: int = 500) -> Optional[str]:
    """Отправляет запрос к LLM через OpenRouter API"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        time.sleep(3)

        result = response.json()
        answer = result['choices'][0]['message']['content'].strip()
        return answer

    except Exception as e:
        print(f"❌ Ошибка при обращении к LLM: {str(e)}")
        return None


def generate_short_summary(competitor_name: str, old_content: str, new_content: str) -> str:
    """Генерирует краткое резюме изменений для конкретного конкурента"""
    prompt = f"""Проанализируй изменения на сайте конкурента "{competitor_name}".

Новый контент сайта (фрагмент):
{new_content[:1500]}

Задача: Напиши 1-2 предложения, описывающие КЛЮЧЕВЫЕ изменения или особенности. Фокусируйся на:
- Новых продуктах/услугах
- Изменениях в ценах
- Акциях и специальных предложениях
- Изменениях в позиционировании

Ответ должен быть кратким и конкретным."""

    summary = call_llm(prompt, max_tokens=200)

    if not summary:
        return f"Обнаружены изменения на сайте {competitor_name}."

    return summary


def generate_overall_report(summaries: List[Dict[str, str]]) -> str:
    """Генерирует общий отчет по всем конкурентам"""
    if not summaries:
        return "Изменений не обнаружено."

    changes_text = "\n\n".join([
        f"**{item['competitor']}:**\n{item['summary']}"
        for item in summaries
    ])

    prompt = f"""Ты - аналитик рынка. Проанализируй изменения у конкурентов и выдели общие тренды.

ИЗМЕНЕНИЯ У КОНКУРЕНТОВ:
{changes_text}

Задача: Напиши краткий аналитический отчет (3-5 предложений) с выводами:
- Какие общие тренды прослеживаются
- На что стоит обратить внимание
- Рекомендации

Ответ должен быть конкретным и полезным для бизнеса."""

    report = call_llm(prompt, max_tokens=400)

    if not report:
        return f"Зафиксированы изменения у {len(summaries)} конкурентов."

    return report


print("✅ Функции работы с LLM загружены")

# ============================================================================
# ЧАСТЬ 6: Генерация PDF отчёта
# ============================================================================

def generate_pdf_report(
    report_date: str,
    total_checked: int,
    changes_list: List[Dict[str, str]],
    errors_list: List[Dict[str, str]],
    overall_analysis: str
) -> str:
    """Генерирует PDF отчёт и возвращает путь к файлу"""
    
    # Путь к файлу
    filename = f"/tmp/competitor_report_{report_date}.pdf"
    
    # Создаём документ
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    # Определяем шрифт (с fallback)
    font_regular = FONT_NAME
    font_bold = f"{FONT_NAME}-Bold" if FONT_NAME == 'DejaVuSans' else 'Helvetica-Bold'
    
    # Стили с поддержкой кириллицы
    title_style = ParagraphStyle(
        'CustomTitle',
        fontName=font_bold,
        fontSize=18,
        spaceAfter=12,
        alignment=1,  # Center
        textColor=colors.HexColor('#1a1a1a')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        fontName=font_bold,
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor('#2c5aa0')
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        fontName=font_regular,
        fontSize=10,
        spaceAfter=6,
        leading=14
    )
    
    bold_style = ParagraphStyle(
        'CustomBold',
        fontName=font_bold,
        fontSize=10,
        spaceAfter=4,
        leading=14
    )
    
    small_style = ParagraphStyle(
        'CustomSmall',
        fontName=font_regular,
        fontSize=9,
        textColor=colors.grey,
        alignment=1
    )
    
    # Контент документа
    content = []
    
    # Заголовок
    content.append(Paragraph("Отчёт мониторинга конкурентов", title_style))
    content.append(Paragraph(f"Дата: {report_date}", small_style))
    content.append(Spacer(1, 12))
    
    # Статистика
    content.append(Paragraph("Статистика", heading_style))
    
    stats_data = [
        ["Показатель", "Значение"],
        ["Проверено сайтов", str(total_checked)],
        ["Обнаружено изменений", str(len(changes_list))],
        ["Не удалось проверить", str(len(errors_list))]
    ]
    
    stats_table = Table(stats_data, colWidths=[100*mm, 50*mm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), font_bold),
        ('FONTNAME', (0, 1), (-1, -1), font_regular),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc'))
    ]))
    content.append(stats_table)
    content.append(Spacer(1, 16))
    
    # Изменения
    if changes_list:
        content.append(Paragraph("Обнаруженные изменения", heading_style))
        
        for i, item in enumerate(changes_list, 1):
            competitor = item.get('competitor', 'Неизвестно')
            summary = item.get('summary', '')
            
            content.append(Paragraph(f"{i}. {competitor}", bold_style))
            content.append(Paragraph(summary, normal_style))
            content.append(Spacer(1, 6))
    
    # Общий анализ
    if overall_analysis and changes_list:
        content.append(Paragraph("Аналитика", heading_style))
        content.append(Paragraph(overall_analysis, normal_style))
        content.append(Spacer(1, 12))
    
    # Ошибки
    if errors_list:
        content.append(Paragraph("Не удалось проверить", heading_style))
        
        errors_data = [["Конкурент", "Причина"]]
        for item in errors_list:
            competitor = item.get('competitor', 'Неизвестно')
            reason = item.get('summary', 'Неизвестно')
            errors_data.append([competitor, reason])
        
        errors_table = Table(errors_data, colWidths=[80*mm, 70*mm])
        errors_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ff9800')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), font_bold),
            ('FONTNAME', (0, 1), (-1, -1), font_regular),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fff3e0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc'))
        ]))
        content.append(errors_table)
    
    # Если нет ни изменений, ни ошибок
    if not changes_list and not errors_list:
        content.append(Paragraph("Результат", heading_style))
        content.append(Paragraph("Изменений на сайтах конкурентов не обнаружено.", normal_style))
    
    # Генерируем PDF
    doc.build(content)
    print(f"✅ PDF отчёт создан: {filename}")
    
    return filename


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
            # Если предыдущее сканирование было страницей защиты, считаем как первое
            if last_hash == "PROTECTION_PAGE":
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
        print(f"   🔑 Предыдущий хеш найден: {previous_hash[:16]}...")
    else:
        print(f"   🆕 Первое сканирование для этого конкурента")

    current_content = fetch_website_content(competitor_url)

    if not current_content:
        print(f"   ❌ Не удалось загрузить сайт")
        return {
            'competitor': competitor_name,
            'summary': 'Сайт недоступен',
            'is_error': True
        }

    # Проверяем на страницу защиты (Cloudflare, Captcha и т.п.)
    if is_protection_page(current_content):
        print(f"   ⚠️ Обнаружена страница защиты (Cloudflare/Captcha)")
        
        # Создаём запись без изменений, но с пометкой
        scan_id = generate_unique_id("scan_")
        scan_result_id = create_scan_result(
            scan_id=scan_id,
            scan_date=scan_date,
            competitor_id=competitor_id,
            new_hash="PROTECTION_PAGE",
            content_changed=False,
            raw_content="",
            llm_summary="Сайт недоступен (защита Cloudflare/Captcha)",
            report_id=None
        )
        
        # НЕ обновляем last_scan_id — чтобы при следующем успешном сканировании 
        # сравнить с предыдущим реальным хешем
        
        return {
            'competitor': competitor_name,
            'summary': 'Защита Cloudflare',
            'is_error': True
        }

    new_hash = calculate_hash(current_content)
    print(f"   ✅ Новый хеш: {new_hash[:16]}...")

    content_changed = (previous_hash is not None) and (new_hash != previous_hash)

    scan_id = generate_unique_id("scan_")

    llm_summary = ""
    summary_dict = None

    if content_changed:
        print(f"   🔔 ИЗМЕНЕНИЯ ОБНАРУЖЕНЫ!")
        print(f"   🤖 Генерация резюме через LLM...")
        llm_summary = generate_short_summary(competitor_name, "", current_content)
        print(f"   📄 Резюме: {llm_summary[:100]}...")

        summary_dict = {
            'competitor': competitor_name,
            'summary': llm_summary,
            'is_error': False
        }
    else:
        print(f"   ✅ Изменений не обнаружено")

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
        print(f"   💾 Запись сканирования создана: {scan_id}")
        update_competitor_last_scan(competitor_id, scan_result_id)
        print(f"   🔗 last_scan_id обновлен")

    return summary_dict


print("✅ Основная логика мониторинга загружена")

# ============================================================================
# ЧАСТЬ 9: Функция для запуска системы мониторинга
# ============================================================================

def run_monitoring_system():
    """Запускает систему мониторинга конкурентов"""
    print("🚀 Запуск системы мониторинга конкурентов...")
    
    # Отправляем уведомление о старте
    send_telegram_message("🚀 <b>Запуск мониторинга конкурентов</b>")

    # 1. Создаем общий отчет
    current_date = datetime.now().strftime("%Y-%m-%d")
    report_id = generate_unique_id("report_")
    summary_report_id = create_summary_report(report_id, current_date)

    if not summary_report_id:
        print("❌ Не удалось создать запись для общего отчета. Мониторинг прерван.")
        send_telegram_message("❌ <b>Ошибка:</b> Не удалось создать отчет")
        return

    print(f"📊 Создан общий отчет: {report_id}")

    # 2. Получаем всех конкурентов
    try:
        competitors_response = supabase.table('competitors').select('*').execute()
        competitors = competitors_response.data
    except Exception as e:
        print(f"❌ Ошибка при получении списка конкурентов: {str(e)}")
        send_telegram_message(f"❌ <b>Ошибка:</b> {str(e)[:200]}")
        return

    total_competitors = len(competitors)
    print(f"🌐 Найдено {total_competitors} конкурентов для сканирования.")

    llm_summaries_for_report = []
    error_summaries = []

    # 3. Сканируем каждого конкурента
    for competitor in competitors:
        summary = scan_competitor(competitor, summary_report_id, current_date)
        if summary:
            if summary.get('is_error'):
                # Ошибки доступа собираем отдельно
                error_summaries.append(summary)
            else:
                llm_summaries_for_report.append(summary)
        time.sleep(2)

    # 4. Генерируем общий LLM анализ
    overall_analysis = ""
    if llm_summaries_for_report:
        print("✏️ Генерируем общий LLM анализ по изменениям...")
        overall_analysis = generate_overall_report(llm_summaries_for_report)
        update_summary_report(summary_report_id, overall_analysis)
        print(f"✅ Общий LLM отчет обновлен в Supabase")

    # 5. Генерируем PDF отчёт
    print("📄 Генерируем PDF отчёт...")
    pdf_path = generate_pdf_report(
        report_date=current_date,
        total_checked=total_competitors,
        changes_list=llm_summaries_for_report,
        errors_list=error_summaries,
        overall_analysis=overall_analysis
    )

    # 6. Отправляем в Telegram
    changes_count = len(llm_summaries_for_report)
    errors_count = len(error_summaries)
    
    # Краткое сообщение со статистикой
    telegram_message = f"""📊 <b>Мониторинг завершён</b>

📅 Дата: {current_date}
🌐 Проверено сайтов: <b>{total_competitors}</b>
🔔 Обнаружено изменений: <b>{changes_count}</b>
⚠️ Не удалось проверить: <b>{errors_count}</b>

📎 Подробный отчёт во вложении"""

    # Отправляем PDF с подписью
    send_telegram_document(pdf_path, telegram_message)
    
    # Удаляем временный файл
    try:
        os.remove(pdf_path)
        print(f"🗑️ Временный PDF удалён")
    except:
        pass

    print("✅ Система мониторинга конкурентов завершила работу.")


print("✅ Функция run_monitoring_system загружена")

# ============================================================================
# ЧАСТЬ 10: ЗАПУСК СИСТЕМЫ
# ============================================================================

if __name__ == "__main__":
    run_monitoring_system()
