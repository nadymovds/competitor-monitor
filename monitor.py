
# ============================================================================
# ЧАСТЬ 1: Установка зависимостей и импорты
# ============================================================================


print("✅ Все зависимости установлены")
# Установка необходимых библиотек (запустить один раз)
!playwright install chromium

# Отключаем предупреждения о небезопасных SSL соединениях
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Импорты
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

# Новые импорты для Playwright
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Применяем nest_asyncio для поддержки вложенных event loop'ов
nest_asyncio.apply()

print("✅ Зависимости установлены и импортированы")

# ============================================================================
# ЧАСТЬ 2: Конфигурация и константы
# ============================================================================

import os

# --- Supabase Credentials ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# --- OpenRouter LLM Credentials ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# --- Настройки ---
REQUEST_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MIN_CONTENT_LENGTH = 300
PLAYWRIGHT_TIMEOUT = 30000

# Инициализация Supabase клиента
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("✅ Конфигурация загружена")
print(f"📊 Supabase URL: {SUPABASE_URL}")
print(f"🤖 LLM модель: {LLM_MODEL}")

# ============================================================================
# ЧАСТЬ 3: Утилиты и вспомогательные функции
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


async def render_page_with_browser(url: str) -> Optional[str]:
    """Загружает страницу через безголовый браузер Playwright"""
    try:
        print(f"   🌐 Запуск браузерного рендеринга (асинхронно)...")

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
# ЧАСТЬ 4: Функции работы с LLM (OpenRouter)
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

Задача: Напиши краткий отчет об изменениях на сайтах конкурентов который включает:
1. Дата отчета
2. Общее количество сайтов, включенных в мониторинг
3. Количество сайтов, на которых были обнаружены изменения
4. Список сайтов с названиями конкурентов и кратко что изменилось

Ответ должен быть структурированным и конкретным."""

    report = call_llm(prompt, max_tokens=800)

    if not report:
        return f"Зафиксированы изменения у {len(summaries)} конкурентов."

    return report


print("✅ Функции работы с LLM загружены")

# ============================================================================
# ЧАСТЬ 5: Функции работы с Supabase
# ============================================================================

def get_previous_hash(competitor_id: str) -> Optional[str]:
    """Получает предыдущий хеш из последней записи сканирования"""
    try:
        # Получаем competitor с last_scan_id
        competitor = supabase.table('competitors').select('last_scan_id').eq('id', competitor_id).single().execute()

        if not competitor.data or not competitor.data.get('last_scan_id'):
            return None

        last_scan_id = competitor.data['last_scan_id']

        # Получаем last_hash из scan_results
        scan_result = supabase.table('scan_results').select('last_hash').eq('id', last_scan_id).single().execute()

        return scan_result.data.get('last_hash') if scan_result.data else None

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


def add_comment_to_competitor(competitor_id: str, comment_text: str, source: str = "Script") -> bool:
    """Добавляет новый комментарий в поле comment"""
    try:
        # Получаем текущие комментарии
        competitor = supabase.table('competitors').select('comment').eq('id', competitor_id).single().execute()

        current_comments = competitor.data.get('comment', []) if competitor.data else []

        # Добавляем новый комментарий
        new_comment = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": source,
            "text": comment_text
        }
        current_comments.append(new_comment)

        # Обновляем запись
        supabase.table('competitors').update({
            'comment': current_comments
        }).eq('id', competitor_id).execute()

        return True

    except Exception as e:
        print(f"❌ Ошибка при добавлении комментария: {str(e)}")
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
# ЧАСТЬ 6: Основная логика мониторинга
# ============================================================================

def scan_competitor(
    competitor: Dict,
    report_id: str,
    scan_date: str
) -> Optional[Dict[str, str]]:
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
        return None

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
            'summary': llm_summary
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
# ЧАСТЬ 7: Функция для запуска системы мониторинга
# ============================================================================

def run_monitoring_system():
    """Запускает систему мониторинга конкурентов"""
    print("🚀 Запуск системы мониторинга конкурентов...")

    # 1. Создаем общий отчет
    current_date = datetime.now().strftime("%Y-%m-%d")
    report_id = generate_unique_id("report_")
    summary_report_id = create_summary_report(report_id, current_date)

    if not summary_report_id:
        print("❌ Не удалось создать запись для общего отчета. Мониторинг прерван.")
        return

    print(f"📊 Создан общий отчет: {report_id}")

    # 2. Получаем всех конкурентов
    try:
        competitors_response = supabase.table('competitors').select('*').execute()
        competitors = competitors_response.data
    except Exception as e:
        print(f"❌ Ошибка при получении списка конкурентов: {str(e)}")
        return

    print(f"🌐 Найдено {len(competitors)} конкурентов для сканирования.")

    llm_summaries_for_report = []

    # 3. Сканируем каждого конкурента
    for competitor in competitors:
        summary = scan_competitor(competitor, summary_report_id, current_date)
        if summary:
            llm_summaries_for_report.append(summary)
        time.sleep(2)

    # 4. Генерируем общий LLM отчет
    if llm_summaries_for_report:
        print("✏️ Генерируем общий LLM отчет по изменениям...")
        overall_llm_report = generate_overall_report(llm_summaries_for_report)
        update_summary_report(summary_report_id, overall_llm_report)
        print(f"✅ Общий LLM отчет обновлен в Supabase")
    else:
        overall_llm_report = "Изменений не обнаружено ни у одного конкурента."
        update_summary_report(summary_report_id, overall_llm_report)
        print("ℹ️ Изменений не обнаружено. Общий отчет обновлен.")

    print("✅ Система мониторинга конкурентов завершила работу.")


print("✅ Функция run_monitoring_system загружена")

# ============================================================================
# ЧАСТЬ 8: ЗАПУСК СИСТЕМЫ
# ============================================================================

if __name__ == "__main__":
    run_monitoring_system()
