# -*- coding: utf-8 -*-

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import os
import hashlib
import json
from functools import lru_cache
import re
import asyncio
import random
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse

import requests
import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from supabase import create_client, Client

print("✅ Зависимости импортированы")

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

SUPABASE_URL        = os.environ.get("SUPABASE_URL")
SUPABASE_KEY        = os.environ.get("SUPABASE_KEY")
GROQ_API_KEY        = os.environ.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")
_group_ids_raw = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "")
TELEGRAM_GROUP_CHAT_IDS = [i.strip() for i in _group_ids_raw.split(",") if i.strip()]
TEST_MODE = False  # переопределяется через --test

YANDEX_API_KEY      = os.environ.get("YANDEX_SEARCH_API_KEY")
YANDEX_FOLDER_ID    = os.environ.get("YANDEX_SEARCH_FOLDER_ID")
GOOGLE_CSE_API_KEY  = os.environ.get("GOOGLE_CSE_API_KEY")
GOOGLE_CSE_ID       = os.environ.get("GOOGLE_CSE_ID")

# === LLM ===
LLM_MODEL   = "llama-3.3-70b-versatile"
LLM_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# === ТАЙМАУТЫ И ЛИМИТЫ ===
REQUEST_TIMEOUT        = 30
PLAYWRIGHT_TIMEOUT     = 30000
MAX_POSTS_PER_CHANNEL  = 100
DELAY_BETWEEN_SOURCES  = 3
MAX_PAGES_PER_WEBSITE  = 2
MAX_YANDEX_PAGES       = 3      # макс страниц Яндекс на термин (10 результатов/страница)
LLM_BATCH_PAUSE        = 4      # сек между LLM-вызовами
MENTIONS_TG_LOOKBACK_DAYS = 8  # глубина поиска в уже собранных TG-постах (дней)

DEFAULT_CSS_CONFIG = {
    "item":  "article, .news-item, .post, .news, .entry",
    "title": "h1, h2, h3, .title, .headline",
    "text":  "p, .content, .excerpt, .summary, .description",
    "date":  "time, .date, [datetime], .published, .timestamp",
    "link":  "a[href]",
}

# === USER-AGENTS ===
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

# === SUPABASE ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === СЕМАФОРЫ (инициализируются в main) ===
browser_semaphore = None
llm_semaphore     = None

def init_semaphores():
    global browser_semaphore, llm_semaphore
    browser_semaphore = asyncio.Semaphore(1)
    llm_semaphore     = asyncio.Semaphore(1)

print("✅ Конфигурация загружена")


# ============================================================================
# УТИЛИТЫ
# ============================================================================

def calculate_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_text(html_or_text: str) -> str:
    if not html_or_text:
        return ""
    soup = BeautifulSoup(html_or_text, "lxml")
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


_QUOTE_RE = re.compile(r'[\"\'«»“”‘’]')
_DASH_RE = re.compile(r'[–—‑−]')
_NONWORD_RE = re.compile(r'[^0-9a-zа-яё\s\-]+', re.IGNORECASE)


def _normalize_for_match(text: str) -> str:
    """Нормализует текст для устойчивого сопоставления терминов."""
    if not text:
        return ""
    s = text.lower()
    s = s.replace("ё", "е")
    s = _QUOTE_RE.sub("", s)
    s = _DASH_RE.sub("-", s)
    s = _NONWORD_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _term_tokens(term_norm: str) -> list[str]:
    return re.findall(r"[0-9a-zа-яё]+", term_norm, flags=re.IGNORECASE)


@lru_cache(maxsize=2048)
def _build_term_regex(term_norm: str) -> re.Pattern | None:
    tokens = _term_tokens(term_norm)
    if not tokens:
        return None
    core = r"[\s\-]+".join(re.escape(t) for t in tokens)
    boundary = r"(?<![0-9A-Za-zА-Яа-яЁё])"
    boundary_end = r"(?![0-9A-Za-zА-Яа-яЁё])"
    return re.compile(boundary + core + boundary_end, re.IGNORECASE)


def term_matches(text: str, term: str) -> bool:
    """Полное совпадение: все токены термина присутствуют в тексте (граница слова)."""
    if not text or not term:
        return False
    text_norm = _normalize_for_match(text)
    term_norm = _normalize_for_match(term)
    rx = _build_term_regex(term_norm)
    if not rx:
        return False
    return bool(rx.search(text_norm))


def find_matching_term(text: str, terms: list[str]) -> str:
    """Первый найденный термин или пустая строка."""
    if not text:
        return ""
    for term in terms or []:
        if term and term_matches(text, term):
            return term
    return ""


def contains_any_term(text: str, terms: list[str]) -> bool:
    """True если хотя бы один термин найден в тексте."""
    return bool(find_matching_term(text, terms))


def extract_match_context(text: str, term: str, window: int = 200) -> str:
    """Возвращает фрагмент текста ±window символов вокруг первого вхождения term."""
    if not text or not term:
        return text[:400] if text else ""
    idx = text.lower().find(term.lower())
    if idx == -1:
        return text[:400]
    start = max(0, idx - window)
    end   = min(len(text), idx + len(term) + window)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix


# Список игнорируемых источников (загружается из БД в run_mentions_monitoring)
IGNORED_PATTERNS: list[str] = []


def is_url_ignored(url: str, patterns: list[str]) -> bool:
    """Возвращает True если URL соответствует одному из игнорируемых паттернов.

    Паттерны без "/" — доменные (skai.online → skai.online + *.skai.online).
    Паттерны с "/"  — путевые  (t.me/skai_online — точное совпадение пути).
    """
    if not url or not patterns:
        return False
    try:
        parsed   = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        path     = parsed.path or ""
    except Exception:
        return False

    for pattern in patterns:
        pattern = pattern.strip().lower()
        if "/" in pattern:
            # Путевой паттерн: t.me/skai_online
            pat_host, pat_path = pattern.split("/", 1)
            pat_path = "/" + pat_path
            if hostname == pat_host and (
                path == pat_path
                or path.startswith(pat_path + "/")
                # Telegram web-preview добавляет /s/ перед username: t.me/s/skai_online/363
                or path == "/s" + pat_path
                or path.startswith("/s" + pat_path + "/")
            ):
                return True
        else:
            # Доменный паттерн с поддоменами
            if hostname == pattern or hostname.endswith("." + pattern):
                return True
    return False


IRRELEVANT_TEXT_PATTERNS = [
    re.compile(r"\b(инн|огрн|кпп|оквэд|устав|учредител|регистрац|юр\.?\s*адрес)\b", re.IGNORECASE),
    re.compile(r"\b(ваканс|резюме|карьер|соискател|отклик|работа в)\b", re.IGNORECASE),
    re.compile(r"\b(каталог компаний|справочник|реестр|карточка компании)\b", re.IGNORECASE),
    re.compile(r"\b(sma)\b.{0,40}\b(connector|antenna|coax|rf|cable|female|male|u\.?fl|ipex)\b", re.IGNORECASE),
    re.compile(r"\b(разъем|коаксиал|антенн)\b.{0,40}\b(sma|u\.?fl|ipex)\b", re.IGNORECASE),
]


def is_obviously_irrelevant(text: str, url: str) -> bool:
    if not text:
        return True
    return any(rx.search(text) for rx in IRRELEVANT_TEXT_PATTERNS)


_VIDEO_URL_RE = re.compile(
    r'(vk\.com/video|vkvideo\.ru|vk\.com/clip'
    r'|yandex\.ru/video|yandex\.ru/efir'
    r'|youtube\.com/watch|music\.youtube\.com|youtu\.be/'
    r'|rutube\.ru/video|ok\.ru/video'
    r'|wall-video\.ru|tiktok\.com/@)',
    re.IGNORECASE,
)


def is_video_url(url: str) -> bool:
    """Возвращает True если URL ведёт на видео-контент."""
    return bool(_VIDEO_URL_RE.search(url))


def get_ignored_patterns() -> list[str]:
    """Загружает паттерны игнорируемых источников из БД."""
    try:
        result = supabase.table("mention_ignored_sources").select("pattern").execute()
        return [row["pattern"] for row in (result.data or []) if row.get("pattern")]
    except Exception as e:
        print(f"⚠️ Не удалось загрузить игнорируемые источники: {e}")
        return []


MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


def parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    s = date_str.strip().lower()
    now = datetime.now()
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        pass
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", s)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), 12, 0, 0)
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, 0, 0)
        except ValueError:
            pass
    for month_name, month_num in MONTHS_RU.items():
        if month_name in s:
            m = re.search(rf"(\d{{1,2}})\s*{month_name}[а-я]*\s*(\d{{4}})?", s)
            if m:
                try:
                    day  = int(m.group(1))
                    year = int(m.group(2)) if m.group(2) else now.year
                    return datetime(year, month_num, day, 12, 0, 0)
                except ValueError:
                    pass
            break
    return None


# ============================================================================
# TELEGRAM УВЕДОМЛЕНИЯ
# ============================================================================

def get_notification_recipients() -> list:
    if TEST_MODE:
        print("⚠️ TEST MODE: уведомления только администратору")
        return [TELEGRAM_CHAT_ID] if TELEGRAM_CHAT_ID else []
    recipients = []
    if TELEGRAM_CHAT_ID:
        recipients.append(TELEGRAM_CHAT_ID)
    try:
        result = supabase.table("users").select("telegram_id").execute()
        for row in result.data or []:
            tid = str(row["telegram_id"])
            if tid not in recipients:
                recipients.append(tid)
    except:
        pass
    return recipients


def send_telegram_message(message: str) -> bool:
    success = False
    for chat_id in get_notification_recipients():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=30)
            success = True
        except:
            pass
    return success


# ============================================================================
# LLM
# ============================================================================

async def call_llm_async(prompt: str, session: aiohttp.ClientSession, max_tokens: int = 500) -> str | None:
    """Вызов Groq API с семафором и retry (паттерн из news_monitor.py)."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    backoff = [5, 15]
    for attempt in range(2):
        try:
            async with llm_semaphore:
                async with session.post(
                    LLM_API_URL, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=90)
                ) as resp:
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        wait = float(retry_after) if retry_after and float(retry_after) < 30 else backoff[attempt]
                        print(f"  ⚠️ Rate limit (429), жду {wait} сек... (попытка {attempt+1}/2)")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt < 1:
                await asyncio.sleep(5)
                print(f"  ⚠️ LLM retry: {e}")
            else:
                print(f"  ❌ LLM ошибка после 2 попыток: {e}")
                return None
    return None


def parse_llm_json(response: str) -> dict | None:
    """Извлечение JSON из ответа LLM."""
    if not response:
        return None
    s = response.strip()
    s = re.sub(r"^```json?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


async def analyze_mention(text: str, url: str, search_term: str,
                          session: aiohttp.ClientSession) -> tuple[str, str, bool]:
    """Определяет тональность, summary и релевантность упоминания через Groq.

    Returns: (sentiment, summary, is_relevant)
    """
    if not text or len(text.strip()) < 20:
        return "neutral", "", False

    if not search_term:
        return "neutral", "", False

    if is_obviously_irrelevant(text, url):
        return "neutral", "", False

    if not term_matches(text, search_term):
        return "neutral", "", False

    prompt = f"""Оцени релевантность поискового результата для мониторинга упоминаний компании.

ПОИСКОВЫЙ ЗАПРОС: «{search_term}»
URL: {url}
ТЕКСТ СНИППЕТА: {text[:2000]}

Ставь is_relevant: false если:
- «{search_term}» просто в списке клиентов/партнёров/портфолио без события
- Аббревиатура ООО/ЗАО/АО совпала случайно с другой компанией
- Сайт — справочник юрлиц (audit-it.ru, rusprofile.ru, focus.kontur.ru, zachestnyibiznes.ru и т.п.)
- TikTok/VK/OK без явной связи с брендом
- Вакансии, резюме, учебные/академические работы

is_relevant: true ТОЛЬКО если: есть конкретное событие, новость, отзыв или обсуждение,
где «{search_term}» — главный субъект, а не строчка в списке.

ТОНАЛЬНОСТЬ (только если is_relevant: true):
- positive — похвала, успех, награда
- negative — критика, жалоба, проблема
- neutral — нейтральный факт

РЕЗЮМЕ (только если is_relevant: true): суть события, до 150 символов, по-русски.

Отвечай ТОЛЬКО JSON:
{{"is_relevant": true, "sentiment": "neutral", "summary": "Краткое описание"}}"""

    response = await call_llm_async(prompt, session, max_tokens=250)
    data = parse_llm_json(response)
    if not data:
        return "neutral", "", False  # при ошибке отсекаем

    is_relevant = bool(data.get("is_relevant", False))
    sentiment = data.get("sentiment", "neutral")
    if sentiment not in ("positive", "negative", "neutral"):
        sentiment = "neutral"
    summary = str(data.get("summary", "")).strip()[:200]
    return sentiment, summary, is_relevant


# ============================================================================
# SUPABASE — ОПЕРАЦИИ
# ============================================================================

def get_search_terms() -> list[str]:
    """Возвращает активные поисковые термины."""
    try:
        result = (supabase.table("mention_search_terms")
                  .select("term")
                  .eq("is_active", True)
                  .execute())
        return [row["term"] for row in (result.data or []) if row.get("term")]
    except Exception as e:
        print(f"❌ Ошибка получения поисковых терминов: {e}")
        return []


def get_mention_sources() -> list:
    """Возвращает активные источники (TG-каналы и веб-порталы)."""
    try:
        result = supabase.table("mention_sources").select("*").eq("is_active", True).execute()
        return result.data or []
    except Exception as e:
        print(f"❌ Ошибка получения источников: {e}")
        return []


def create_scan() -> int | None:
    """Создаёт запись о запуске скрипта. Возвращает scan_id."""
    try:
        result = supabase.table("mention_scans").insert({
            "scan_date": datetime.now().date().isoformat(),
            "status": "running",
        }).execute()
        if result.data:
            scan_id = result.data[0]["id"]
            print(f"✅ Скан создан (ID: {scan_id})")
            return scan_id
        return None
    except Exception as e:
        print(f"❌ Ошибка создания скана: {e}")
        return None


def complete_scan(scan_id: int, mentions_count: int) -> None:
    """Помечает скан завершённым."""
    try:
        supabase.table("mention_scans").update({
            "status": "completed",
            "mentions_found": mentions_count,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", scan_id).execute()
    except Exception as e:
        print(f"⚠️ Ошибка завершения скана: {e}")


def fail_scan(scan_id: int, error: str) -> None:
    """Помечает скан как упавший."""
    try:
        supabase.table("mention_scans").update({
            "status": "failed",
            "error_message": error[:500],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", scan_id).execute()
    except:
        pass


def save_mention(data: dict) -> bool:
    """INSERT упоминания. При дубликате URL обновляет scan_id (чтобы запись была видна
    в текущем скане), но сохраняет оригинальный created_at (дата первого обнаружения).
    Возвращает True если запись новая."""
    url = data.get("url", "")
    if url and is_url_ignored(url, IGNORED_PATTERNS):
        print(f"  🚫 Игнорируем (в списке исключений): {url[:80]}")
        return False
    try:
        result = supabase.table("mentions").insert(data).execute()
        return bool(result.data)
    except Exception as e:
        err = str(e)
        # Supabase возвращает 23505 при конфликте уникального ключа (url)
        if "23505" in err or "duplicate" in err.lower() or "already exists" in err.lower():
            # Обновляем scan_id чтобы дубликат был виден в текущем скане
            try:
                supabase.table("mentions").update({
                    "scan_id": data.get("scan_id"),
                }).eq("url", data["url"]).execute()
            except Exception:
                pass
            return False  # не новая запись
        print(f"  ⚠️ Ошибка сохранения упоминания: {e}")
        return False


def get_unprocessed_mentions() -> list:
    """Выборка необработанных упоминаний для LLM-анализа."""
    try:
        result = (supabase.table("mentions")
                  .select("id, url, title, content_snippet, search_term")
                  .eq("is_processed", False)
                  .order("created_at", desc=False)
                  .execute())
        return result.data or []
    except Exception as e:
        print(f"❌ Ошибка получения необработанных упоминаний: {e}")
        return []


def update_mention_analysis(mention_id: int, sentiment: str, summary: str) -> None:
    """Сохраняет результат LLM-анализа."""
    try:
        supabase.table("mentions").update({
            "sentiment": sentiment,
            "summary": summary,
            "is_processed": True,
        }).eq("id", mention_id).execute()
    except Exception as e:
        print(f"  ⚠️ Ошибка обновления упоминания {mention_id}: {e}")


def delete_mention(mention_id: int) -> None:
    """Удаляет нерелевантное упоминание из БД."""
    try:
        supabase.table("mentions").delete().eq("id", mention_id).execute()
    except Exception as e:
        print(f"  ⚠️ Ошибка удаления упоминания {mention_id}: {e}")


# ============================================================================
# ПОИСК: GOOGLE CSE
# ============================================================================

async def search_google(term: str, session: aiohttp.ClientSession) -> list[dict]:
    """Поиск через Google Custom Search Engine."""
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_ID:
        print("  ⚠️ Google CSE не настроен, пропуск")
        return []

    api_query = re.sub(r"\s+", " ", re.sub(r"[.\-]+", " ", term)).strip()
    params = {
        "key":          GOOGLE_CSE_API_KEY,
        "cx":           GOOGLE_CSE_ID,
        "q":            f'"{api_query}"',
        "num":          10,
        "dateRestrict": "w1",
    }

    try:
        async with session.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            if resp.status == 429:
                print("  ⚠️ Google CSE: rate limit")
                return []
            resp.raise_for_status()
            data = await resp.json()

        items = data.get("items", [])
        results = []
        for item in items:
            url = item.get("link", "")
            if not url:
                continue
            pagemap  = item.get("pagemap", {})
            metatags = (pagemap.get("metatags") or [{}])[0]
            date_str = (
                metatags.get("article:published_time")
                or metatags.get("og:updated_time")
                or ""
            )
            results.append({
                "title":         item.get("title", "")[:500],
                "url":           url,
                "content_snippet": item.get("snippet", "")[:1000],
                "post_date":     parse_date(date_str),
                "source_type":   "yandex",   # will override below
                "search_term":   term,
                "source_name":   "Google",
            })
            results[-1]["source_type"] = "website"  # Google возвращает веб-страницы

        print(f"  🔵 Google CSE «{term}»: {len(results)} результатов")
        return results

    except Exception as e:
        print(f"  ❌ Ошибка Google CSE: {e}")
        return []


# ============================================================================
# ПОИСК: YANDEX SEARCH API
# ============================================================================

async def _search_yandex_page(term: str, page: int, session: aiohttp.ClientSession) -> list[dict]:
    """Получает одну страницу результатов Yandex Search API v2."""
    import base64
    import xml.etree.ElementTree as ET

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type":  "application/json",
    }
    api_query = re.sub(r"\s+", " ", re.sub(r"[.\-]+", " ", term)).strip()
    body = {
        "folderId": YANDEX_FOLDER_ID,
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText":  f'"{api_query}"',
            "maxPassages": 1,
            "page": page,
        },
        "sortSpec": {"sortMode": "SORT_MODE_BY_TIME", "sortOrder": "SORT_ORDER_DESC"},
        "maxPassages": 1,
        "groupsOnPage": 10,
    }

    # 1. Запускаем асинхронный поиск
    try:
        async with session.post(
            "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync",
            headers=headers,
            json=body,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            resp.raise_for_status()
            operation = await resp.json()
    except Exception as e:
        print(f"  ❌ Yandex Search стр.{page} (запуск): {e}")
        return []

    operation_id = operation.get("id")
    if not operation_id:
        print(f"  ❌ Yandex Search стр.{page}: не получен operation_id")
        return []

    # 2. Опрашиваем операцию (макс 30 сек)
    op_url = f"https://operation.api.cloud.yandex.net/operations/{operation_id}"
    result_data = None
    for _ in range(10):
        await asyncio.sleep(3)
        try:
            async with session.get(
                op_url, headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                op = await resp.json()
        except Exception as e:
            print(f"  ⚠️ Yandex Operation poll стр.{page}: {e}")
            break

        if op.get("done"):
            result_data = op.get("response") or op.get("result")
            break

    if not result_data:
        print(f"  ⚠️ Yandex «{term}» стр.{page}: операция не завершилась или пустой ответ")
        return []

    # 3. Парсим base64-encoded XML
    raw_data = result_data.get("rawData") or result_data.get("raw_data")
    if not raw_data:
        print(f"  ⚠️ Yandex «{term}» стр.{page}: нет поля rawData")
        return []

    try:
        xml_bytes = base64.b64decode(raw_data)
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        print(f"  ❌ Yandex «{term}» стр.{page}: ошибка декодирования XML: {e}")
        return []

    results = []
    for doc in root.findall(".//{http://www.yandex.ru/XMLsearch}doc") or root.findall(".//doc"):
        url_el = doc.find("{http://www.yandex.ru/XMLsearch}url") or doc.find("url")
        url = url_el.text.strip() if url_el is not None and url_el.text else ""
        if not url:
            continue

        title_el = doc.find("{http://www.yandex.ru/XMLsearch}title") or doc.find("title")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""

        snippet = ""
        for tag in ["passages", "extended-text", "headline"]:
            ns_el = doc.find(f"{{http://www.yandex.ru/XMLsearch}}{tag}") or doc.find(tag)
            if ns_el is not None:
                snippet = "".join(ns_el.itertext()).strip()[:1000]
                break

        modtime_el = doc.find("{http://www.yandex.ru/XMLsearch}modtime") or doc.find("modtime")
        date_str = modtime_el.text.strip() if modtime_el is not None and modtime_el.text else ""

        results.append({
            "title":           title[:500],
            "url":             url,
            "content_snippet": snippet,
            "post_date":       parse_date(date_str),
            "source_type":     "yandex",
            "search_term":     term,
            "source_name":     "Яндекс",
        })

    return results


async def search_yandex(term: str, session: aiohttp.ClientSession) -> list[dict]:
    """Поиск через Yandex Search API v2: до MAX_YANDEX_PAGES страниц по 10 результатов."""
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        print("  ⚠️ Yandex Search API не настроен, пропуск")
        return []

    all_results = []
    for page in range(MAX_YANDEX_PAGES):
        page_results = await _search_yandex_page(term, page, session)
        all_results.extend(page_results)
        # Если страница вернула меньше 10 — это последняя
        if len(page_results) < 10:
            break
        if page < MAX_YANDEX_PAGES - 1:
            await asyncio.sleep(1)

    if not all_results:
        print(f"  ⚠️ Yandex «{term}»: 0 результатов")
    else:
        print(f"  ✅ Yandex «{term}»: {len(all_results)} результатов ({min(MAX_YANDEX_PAGES, (len(all_results) + 9) // 10)} стр.)")
    return all_results


# ============================================================================
# СКАНИРОВАНИЕ TG-КАНАЛОВ (через t.me/s/ + Playwright)
# ============================================================================

async def fetch_tg_page(username: str, browser_context, before_id: int = None) -> str:
    url = f"https://t.me/s/{username}"
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
            """)
            await page.route("**/*.{mp4,webm,mp3,wav}", lambda route: route.abort())
            await page.route("**/*google-analytics*", lambda route: route.abort())
            await page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT)
            try:
                await page.wait_for_selector("div.tgme_widget_message_wrap", timeout=15000)
            except PlaywrightTimeout:
                return ""
            return await page.content()
        except Exception as e:
            print(f"  ❌ TG fetch @{username}: {e}")
            return ""
        finally:
            await page.close()


def parse_tg_posts(html: str, username: str) -> list[dict]:
    if not html:
        return []
    soup  = BeautifulSoup(html, "lxml")
    wraps = soup.find_all("div", class_="tgme_widget_message_wrap")
    posts = []
    for wrap in wraps:
        try:
            msg = wrap.find("div", class_="tgme_widget_message")
            if not msg:
                continue
            data_post = msg.get("data-post", "")
            if "/" not in data_post:
                continue
            message_id = int(data_post.split("/")[-1])

            text_div = msg.find("div", class_="tgme_widget_message_text")
            text = clean_text(str(text_div)) if text_div else ""

            time_tag = msg.find("time")
            post_date = None
            if time_tag and time_tag.get("datetime"):
                post_date = parse_date(time_tag["datetime"])

            posts.append({
                "message_id": message_id,
                "post_url":   f"https://t.me/{username}/{message_id}",
                "text":       text,
                "post_date":  post_date,
            })
        except Exception:
            continue
    return sorted(posts, key=lambda p: p["message_id"])


async def scan_tg_channel(source: dict, terms: list[str], browser_context) -> list[dict]:
    """Сканирует TG-канал, фильтрует посты по вхождению терминов."""
    username = source.get("username", "").lstrip("@")
    if not username:
        return []

    print(f"\n  📱 TG-канал @{username}")
    all_posts   = []
    before_id   = None
    pages_done  = 0

    while pages_done < 5:
        html = await fetch_tg_page(username, browser_context, before_id)
        if not html:
            break
        page_posts = parse_tg_posts(html, username)
        if not page_posts:
            break
        all_posts.extend(page_posts)
        if len(parse_tg_posts(html, username)) < 10:
            break
        before_id  = min(p["message_id"] for p in page_posts)
        pages_done += 1
        await asyncio.sleep(1)

    # Фильтрация по вхождению терминов
    matched = []
    for p in all_posts:
        text = p.get("text") or ""
        if not text:
            continue
        term = find_matching_term(text, terms)
        if not term:
            continue
        p["__matched_term"] = term
        matched.append(p)

    results = []
    for p in matched[:MAX_POSTS_PER_CHANNEL]:
        snippet = p["text"][:1000]
        if is_obviously_irrelevant(p.get("text") or "", p.get("post_url") or ""):
            continue
        results.append({
            "url":             p["post_url"],
            "title":           p["text"][:150].split("\n")[0],
            "content_snippet": snippet,
            "post_date":       p["post_date"],
            "source_type":     "telegram",
            "source_name":     source.get("title") or f"@{username}",
            "search_term":     p.get("__matched_term", ""),
        })

    print(f"    ✅ Найдено постов: {len(all_posts)}, с упоминаниями: {len(results)}")
    return results


# ============================================================================
# СКАНИРОВАНИЕ ВЕБ-ПОРТАЛОВ (CSS-скрейпинг + Playwright)
# ============================================================================

async def fetch_web_page(url: str, browser_context) -> str:
    async with browser_semaphore:
        page = await browser_context.new_page()
        try:
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)
            await page.route("**/*.{mp4,webm,mp3,wav,avi,mov}", lambda route: route.abort())
            await page.route("**/*google-analytics*", lambda route: route.abort())
            await page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT)
            await page.wait_for_timeout(2000)
            html = await page.content()
            return html if len(html) > 500 else ""
        except Exception as e:
            print(f"    ❌ Fetch {url}: {e}")
            return ""
        finally:
            try:
                await page.close()
            except:
                pass


def parse_articles_from_html(html: str, base_url: str, css_config: dict) -> list[dict]:
    """Парсит статьи из HTML по CSS-селекторам (паттерн из news_monitor.py)."""
    if not html:
        return []

    cfg  = css_config or DEFAULT_CSS_CONFIG
    soup = BeautifulSoup(html, "lxml")

    item_selectors = [s.strip() for s in cfg.get("item", "").split(",")]
    items = []
    for sel in item_selectors:
        if sel:
            items.extend(soup.select(sel))
    if not items:
        return []

    results = []
    for item in items[:30]:
        try:
            title = ""
            for sel in [s.strip() for s in cfg.get("title", "").split(",")]:
                el = sel and item.select_one(sel)
                if el:
                    title = el.get_text(strip=True)
                    break

            text = ""
            for sel in [s.strip() for s in cfg.get("text", "").split(",")]:
                els = sel and item.select(sel)
                if els:
                    text = " ".join(e.get_text(strip=True) for e in els)
                    break

            if not title and not text:
                continue

            post_date = None
            for sel in [s.strip() for s in cfg.get("date", "").split(",")]:
                el = sel and item.select_one(sel)
                if el:
                    dt = el.get("datetime") or el.get_text(strip=True)
                    post_date = parse_date(dt)
                    if post_date:
                        break

            article_url = ""
            for sel in [s.strip() for s in cfg.get("link", "").split(",")]:
                el = sel and item.select_one(sel)
                if el and el.get("href"):
                    article_url = urljoin(base_url, el["href"])
                    break

            results.append({
                "title":     title[:500],
                "text":      text[:2000],
                "post_date": post_date,
                "url":       article_url or base_url,
            })
        except Exception:
            continue

    return results


async def scan_website(source: dict, terms: list[str], browser_context) -> list[dict]:
    """Сканирует веб-портал, фильтрует статьи по вхождению терминов."""
    url   = source.get("url", "")
    title = source.get("title") or url
    if not url:
        return []

    print(f"\n  🌐 Веб-портал: {title} ({url})")

    css_config = source.get("css_config") or DEFAULT_CSS_CONFIG

    html = await fetch_web_page(url, browser_context)
    if not html:
        print(f"    ❌ Не удалось загрузить страницу")
        return []

    articles = parse_articles_from_html(html, url, css_config)
    if not articles:
        print(f"    ⚠️ CSS-парсер ничего не нашёл")
        return []

    # Фильтрация по вхождению терминов
    matched = []
    for a in articles:
        combined = f"{a['title']} {a['text']}"
        term = find_matching_term(combined, terms)
        if not term:
            continue
        a["__matched_term"] = term
        matched.append(a)

    results = []
    for a in matched:
        snippet = (a["text"] or a["title"])[:1000]
        combined = f"{a['title']} {a['text']}"
        if is_obviously_irrelevant(combined, a.get("url") or ""):
            continue
        results.append({
            "url":             a["url"],
            "title":           a["title"],
            "content_snippet": snippet,
            "post_date":       a["post_date"],
            "source_type":     "website",
            "source_name":     title,
            "search_term":     a.get("__matched_term", ""),
        })

    print(f"    ✅ Найдено статей: {len(articles)}, с упоминаниями: {len(results)}")
    return results


# ============================================================================
# LLM-ОБРАБОТКА НЕОБРАБОТАННЫХ УПОМИНАНИЙ
# ============================================================================

async def process_unprocessed_mentions(session: aiohttp.ClientSession) -> tuple[int, int]:
    """Обрабатывает все необработанные упоминания через LLM пачками.

    Returns: (processed_count, deleted_count)
    """
    mentions = get_unprocessed_mentions()
    if not mentions:
        print("  ℹ️ Необработанных упоминаний нет")
        return 0, 0

    print(f"  🤖 Обрабатываю {len(mentions)} упоминаний через LLM...")
    processed = 0
    deleted   = 0

    for i, mention in enumerate(mentions):
        try:
            text        = mention.get("content_snippet") or mention.get("title") or ""
            search_term = mention.get("search_term") or ""
            sentiment, summary, is_relevant = await analyze_mention(
                text, mention.get("url", ""), search_term, session
            )
            if not is_relevant:
                delete_mention(mention["id"])
                deleted += 1
                print(f"    [{i+1}/{len(mentions)}] ID={mention['id']} → ❌ НЕРЕЛЕВАНТНО, удалено")
            else:
                update_mention_analysis(mention["id"], sentiment, summary)
                processed += 1
                print(f"    [{i+1}/{len(mentions)}] ID={mention['id']} → {sentiment} | {summary[:60]}")
        except Exception as e:
            print(f"    ❌ Ошибка обработки {mention['id']}: {e}")

        if i < len(mentions) - 1:
            await asyncio.sleep(LLM_BATCH_PAUSE)

    return processed, deleted


# ============================================================================
# ПОИСК УПОМИНАНИЙ В УЖЕ СОБРАННЫХ TG-ПОСТАХ (конкуренты + новости)
# ============================================================================

def find_mentions_in_competitor_posts(scan_id: int | None, terms: list[str]) -> int:
    """Ищет упоминания терминов в уже собранных постах TG-каналов конкурентов.

    Не запускает браузер — читает данные из таблицы competitor_tg_posts.
    Возвращает количество новых упоминаний.
    """
    since_date = (datetime.now() - timedelta(days=MENTIONS_TG_LOOKBACK_DAYS)).isoformat()

    try:
        result = (supabase.table("competitor_tg_posts")
                  .select("channel_username, post_url, content_text, post_date")
                  .gte("post_date", since_date)
                  .execute())
        posts = result.data or []
    except Exception as e:
        print(f"  ❌ Ошибка запроса competitor_tg_posts: {e}")
        return 0

    print(f"  📥 competitor_tg_posts за {MENTIONS_TG_LOOKBACK_DAYS} дн.: {len(posts)} постов")

    new_count = 0
    for post in posts:
        text = post.get("content_text") or ""
        if not text:
            continue
        url = post.get("post_url", "")
        if not url:
            continue
        matched_term = find_matching_term(text, terms)
        if not matched_term:
            continue
        if is_obviously_irrelevant(text, url=url):
            continue
        snippet = extract_match_context(text, matched_term, window=200)

        channel = post.get("channel_username", "")
        source_name = f"@{channel.lstrip('@')}" if channel else "конкурент TG"

        data = {
            "scan_id":         scan_id,
            "source_type":     "telegram",
            "url":             url,
            "title":           text[:150].split("\n")[0],
            "content_snippet": snippet[:1000],
            "post_date":       post.get("post_date"),
            "search_term":     matched_term[:255],
            "source_name":     source_name[:255],
            "is_processed":    False,
        }
        if save_mention(data):
            new_count += 1
            print(f"    ✅ Конкурент TG: {url[:80]}")

    return new_count


def find_mentions_in_news_posts(scan_id: int | None, terms: list[str]) -> int:
    """Ищет упоминания терминов в уже собранных постах отраслевых новостных TG-каналов.

    Не запускает браузер — читает данные из таблицы news_posts.
    Возвращает количество новых упоминаний.
    """
    since_date = (datetime.now() - timedelta(days=MENTIONS_TG_LOOKBACK_DAYS)).isoformat()

    # Загружаем каналы для маппинга channel_id → username/title
    try:
        channels_result = supabase.table("news_channels").select("id, username, title").execute()
        channel_map = {row["id"]: row for row in (channels_result.data or [])}
    except Exception as e:
        print(f"  ⚠️ Ошибка запроса news_channels: {e}")
        channel_map = {}

    try:
        result = (supabase.table("news_posts")
                  .select("channel_id, post_url, content_text, post_date, source_type")
                  .gte("post_date", since_date)
                  .execute())
        posts = result.data or []
    except Exception as e:
        print(f"  ❌ Ошибка запроса news_posts: {e}")
        return 0

    print(f"  📥 news_posts за {MENTIONS_TG_LOOKBACK_DAYS} дн.: {len(posts)} постов")

    new_count = 0
    for post in posts:
        text = post.get("content_text") or ""
        if not text:
            continue
        url = post.get("post_url", "")
        if not url:
            continue
        matched_term = find_matching_term(text, terms)
        if not matched_term:
            continue
        if is_obviously_irrelevant(text, url=url):
            continue
        snippet = extract_match_context(text, matched_term, window=200)

        channel = channel_map.get(post.get("channel_id"), {})
        post_source_type = post.get("source_type") or "telegram"
        username = channel.get("username", "")
        if post_source_type == "website":
            source_name = channel.get("title") or "новости портал"
        else:
            source_name = f"@{username.lstrip('@')}" if username else (channel.get("title") or "новости TG")

        data = {
            "scan_id":         scan_id,
            "source_type":     post_source_type,
            "url":             url,
            "title":           text[:150].split("\n")[0],
            "content_snippet": snippet[:1000],
            "post_date":       post.get("post_date"),
            "search_term":     matched_term[:255],
            "source_name":     source_name[:255],
            "is_processed":    False,
        }
        if save_mention(data):
            new_count += 1
            print(f"    ✅ Новости TG: {url[:80]}")

    return new_count


# ============================================================================
# ОРКЕСТРАТОР
# ============================================================================

async def run_mentions_monitoring():
    print("\n" + "=" * 60)
    print("МОНИТОРИНГ УПОМИНАНИЙ — ОТКЛЮЧЁН")
    print("=" * 60)
    print("ℹ️ Мониторинг упоминаний временно отключён.")
    return

    # 1. Создаём запись о запуске
    scan_id = create_scan()

    # 2. Загружаем данные
    global IGNORED_PATTERNS
    IGNORED_PATTERNS = get_ignored_patterns()
    print(f"🚫 Игнорируемых источников: {len(IGNORED_PATTERNS)}")

    search_terms = get_search_terms()  # list[str]
    if not search_terms:
        msg = "❌ Нет активных поисковых терминов — мониторинг упоминаний отменён"
        print(msg)
        send_telegram_message(msg)
        if scan_id:
            fail_scan(scan_id, "Нет активных поисковых терминов")
        return

    sources = get_mention_sources()
    tg_sources  = [s for s in sources if s.get("source_type") == "telegram"]
    web_sources = [s for s in sources if s.get("source_type") == "website"]

    print(f"🔍 Поисковые термины ({len(search_terms)}): {', '.join(search_terms)}")
    print(f"📱 TG-каналов: {len(tg_sources)}, 🌐 Веб-порталов: {len(web_sources)}")

    all_results: list[dict] = []
    comp_tg_count = 0
    news_tg_count = 0

    connector = aiohttp.TCPConnector(limit=5, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as http_session:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            browser_context = await browser.new_context(
                user_agent=get_random_user_agent(),
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8"},
            )

            # === ФАЗА 1A: Поиск Google CSE ===
            if GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID:
                print("\n" + "=" * 60)
                print("ФАЗА 1A: GOOGLE CSE")
                print("=" * 60)
                for term in search_terms:
                    results = await search_google(term, http_session)
                    all_results.extend(results)
                    await asyncio.sleep(1)

            # === ФАЗА 1B: Поиск Yandex ===
            if YANDEX_API_KEY and YANDEX_FOLDER_ID:
                print("\n" + "=" * 60)
                print("ФАЗА 1B: YANDEX SEARCH API")
                print("=" * 60)
                for term in search_terms:
                    results = await search_yandex(term, http_session)
                    all_results.extend(results)
                    await asyncio.sleep(2)

            # === ФАЗА 1C: TG-каналы ===
            if tg_sources:
                print("\n" + "=" * 60)
                print("ФАЗА 1C: TG-КАНАЛЫ")
                print("=" * 60)
                for i, source in enumerate(tg_sources, 1):
                    print(f"\n[{i}/{len(tg_sources)}] {source.get('title') or source.get('username')}")
                    results = await scan_tg_channel(source, search_terms, browser_context)
                    all_results.extend(results)
                    if i < len(tg_sources):
                        await asyncio.sleep(DELAY_BETWEEN_SOURCES)

            # === ФАЗА 1D: Веб-порталы ===
            if web_sources:
                print("\n" + "=" * 60)
                print("ФАЗА 1D: ВЕБ-ПОРТАЛЫ")
                print("=" * 60)
                for i, source in enumerate(web_sources, 1):
                    print(f"\n[{i}/{len(web_sources)}] {source.get('title') or source.get('url')}")
                    results = await scan_website(source, search_terms, browser_context)
                    all_results.extend(results)
                    if i < len(web_sources):
                        await asyncio.sleep(DELAY_BETWEEN_SOURCES)

            await browser_context.close()
            await browser.close()

        # === ФАЗА 2: Сохранение (дедупликация по URL) ===
        print("\n" + "=" * 60)
        print(f"ФАЗА 2: СОХРАНЕНИЕ ({len(all_results)} результатов)")
        print("=" * 60)

        new_count    = 0
        seen_urls: set[str] = set()

        for item in all_results:
            url = item.get("url", "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            term    = item.get("search_term", "")
            title   = item.get("title", "")
            snippet = item.get("content_snippet", "")

            # Фильтр видео-URL — не сохраняем ссылки на видео-платформы
            if is_video_url(url):
                print(f"  🎬 Пропуск видео-URL: {url[:80]}")
                continue
            if not term:
                print(f"  🚫 Пустой термин: {url[:80]}")
                continue

            combined = f"{title} {snippet}"
            if not term_matches(combined, term):
                print(f"  ⏭️  Пропуск (термин не найден в сниппете): {url[:80]}")
                continue

            if is_obviously_irrelevant(combined, url):
                print(f"  🚫 Нерелевантный контент: {url[:80]}")
                continue

            # Для всех источников: обрезаем snippet до контекстного окна вокруг keyword
            if term and snippet:
                snippet = extract_match_context(snippet, term, window=200)

            post_date = item.get("post_date")
            data = {
                "scan_id":         scan_id,
                "source_type":     item.get("source_type", "website"),
                "url":             url,
                "title":           title[:500],
                "content_snippet": snippet[:1000],
                "post_date":       post_date.isoformat() if post_date else None,
                "search_term":     term[:255],
                "source_name":     item.get("source_name", "")[:255],
                "is_processed":    False,
            }
            if save_mention(data):
                new_count += 1
                print(f"  ✅ Новое упоминание: {url[:80]}")
            else:
                print(f"  🔁 Дубликат: {url[:80]}")

        print(f"\n📊 Сохранено новых упоминаний: {new_count} из {len(all_results)} найденных")

        # === ФАЗА 2E: Упоминания из TG конкурентов и новостных каналов ===
        print("\n" + "=" * 60)
        print("ФАЗА 2E: ПОИСК УПОМИНАНИЙ В TG КОНКУРЕНТОВ И НОВОСТЯХ")
        print("=" * 60)
        comp_tg_count = find_mentions_in_competitor_posts(scan_id, search_terms)
        news_tg_count = find_mentions_in_news_posts(scan_id, search_terms)
        new_count += comp_tg_count + news_tg_count
        print(f"  ✅ Из TG конкурентов: {comp_tg_count}, из TG новостей: {news_tg_count}")

        # === ФАЗА 3: LLM-обработка ===
        print("\n" + "=" * 60)
        print("ФАЗА 3: LLM-АНАЛИЗ ТОНАЛЬНОСТИ")
        print("=" * 60)
        processed_count, deleted_count = await process_unprocessed_mentions(http_session)
        print(f"✅ Обработано LLM: {processed_count}, удалено нерелевантных: {deleted_count}")

    # Завершение
    elapsed = int(time.time() - start_time)
    if scan_id:
        complete_scan(scan_id, new_count)

    summary_msg = f"""📣 <b>Мониторинг упоминаний завершён</b>

🔍 Поисковых терминов: <b>{len(search_terms)}</b>
📱 TG-каналов: <b>{len(tg_sources)}</b>
🌐 Веб-порталов: <b>{len(web_sources)}</b>

🆕 Новых упоминаний: <b>{new_count}</b>
  └ из TG конкурентов: {comp_tg_count}, из TG новостей: {news_tg_count}
🤖 Обработано LLM: <b>{processed_count}</b>
🗑 Удалено нерелевантных: <b>{deleted_count}</b>
⏱️ Время: {elapsed} сек"""

    print(f"\n{summary_msg}")
    # send_telegram_message(summary_msg)  # отключено
    print(f"\n✅ Мониторинг упоминаний завершён за {elapsed} сек")


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='Тестовый режим: уведомления только администратору')
    args = parser.parse_args()
    if args.test:
        TEST_MODE = True
    init_semaphores()
    asyncio.run(run_mentions_monitoring())
