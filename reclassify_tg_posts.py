# -*- coding: utf-8 -*-
"""
Скрипт для реклассификации TG-постов конкурентов.
Получает все посты с category='technical' и переклассифицирует их через LLM.
"""

import os
import re
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, List
from supabase import create_client, Client

# Конфигурация
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

LLM_MODEL = "llama-3.3-70b-versatile"
LLM_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Категории
CATEGORY_PRODUCTS = "products"
CATEGORY_PRICES = "prices"
CATEGORY_NEWS = "news"
CATEGORY_TECHNICAL = "technical"
CATEGORY_SERVICES = "services"
CATEGORY_OTHER = "other"

VALID_CATEGORIES = [CATEGORY_PRODUCTS, CATEGORY_PRICES, CATEGORY_NEWS, CATEGORY_TECHNICAL, CATEGORY_SERVICES, CATEGORY_OTHER]

TAGS = {
    "новый_продукт", "оборудование", "тахографы", "мониторинг", "ПО",
    "акция", "скидка", "бесплатно", "новость", "важное", "партнёрство",
    "законодательство", "wialon", "глонасс"
}

# Ограничение параллельных запросов к LLM
MAX_CONCURRENT_LLM = 3
DELAY_BETWEEN_BATCHES = 2


def check_env():
    """Проверяет наличие необходимых переменных окружения."""
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")

    if missing:
        print(f"Ошибка: отсутствуют переменные окружения: {', '.join(missing)}")
        return False
    return True


async def call_llm_async(prompt: str, session: aiohttp.ClientSession, max_tokens: int = 400) -> str | None:
    """Вызов LLM через Groq API."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }

    for attempt in range(2):
        try:
            async with session.post(LLM_API_URL, json=payload, headers=headers, timeout=30) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result['choices'][0]['message']['content'].strip()
                elif resp.status == 429:
                    # Rate limit - ждём и повторяем
                    await asyncio.sleep(5)
                else:
                    print(f"   LLM error: {resp.status}")
        except Exception as e:
            if attempt < 1:
                await asyncio.sleep(3)
            else:
                print(f"   LLM exception: {e}")
                return None
    return None


def parse_llm_json_response(response: str, competitor_name: str) -> Dict[str, Any]:
    """Парсит JSON-ответ от LLM."""
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

        if result.get("category") not in VALID_CATEGORIES:
            result["category"] = CATEGORY_OTHER

        valid_tags = [t for t in result.get("tags", []) if t in TAGS]
        result["tags"] = valid_tags[:3]

        summary = result.get("summary", "")
        summary = re.sub(r'```.*', '', summary)
        summary = re.sub(r'\{.*', '', summary)
        summary = ' '.join(summary.split()).strip()

        if len(summary) > 500:
            summary = summary[:497] + '...'

        result["summary"] = summary
        return result

    except json.JSONDecodeError:
        return default_result


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

ЗАДАЧА: Определи категорию и кратко опиши суть поста.

ВАЖНО (is_meaningful: true) — только посты про:
- Продукты/услуги: новые устройства, трекеры, тахографы, ПО, платформы, обновления
- Цены: акции, скидки, изменение тарифов, спецпредложения, бесплатный период
- Условия обслуживания: SLA, тарифные планы, техподдержка, условия работы, сервисные пакеты
- Операционные изменения: сбои систем, сервисные объявления, важные изменения в работе
- Новости компании: партнёрства, мероприятия, выставки, сертификация

ИГНОРИРУЙ (категория "other", is_meaningful: false):
- Поздравления с праздниками, развлекательный контент
- Репосты без отношения к продуктам/услугам компании
- Общие мотивационные посты без конкретики
- Законодательство (если не влияет напрямую на продукты компании)
- Награды, рейтинги, общий PR без конкретики о продуктах

ВАЖНЫЕ ПРАВИЛА:
- Отвечай ТОЛЬКО на русском языке
- Описывай только то, что реально содержится в посте
- Не выдумывай информацию

КАТЕГОРИИ (выбери ОДНУ):
1. "products" — новый/обновлённый продукт, устройство, трекер, тахограф, ПО, платформа, обновление
2. "prices" — акция, скидка, изменение цен/тарифов, спецпредложение, бесплатный период
3. "services" — условия обслуживания, SLA, тарифные планы, техподдержка, условия работы
4. "news" — новости компании, партнёрства, мероприятия, выставки, сертификация
5. "other" — нерелевантный контент (поздравления, развлечения, общие репосты)

ФОРМАТ ОТВЕТА (только JSON, без пояснений):
{{
    "category": "products|prices|services|news|other",
    "summary": "Краткое описание сути поста. 1-2 предложения.",
    "tags": ["тег1", "тег2"],
    "is_meaningful": true/false
}}

ТЕГИ: новый_продукт, оборудование, тахографы, мониторинг, ПО, акция, скидка, бесплатно, новость, важное, партнёрство, законодательство, wialon, глонасс"""

    response = await call_llm_async(prompt, session, max_tokens=400)
    return parse_llm_json_response(response, competitor_name)


async def process_post(post: dict, session: aiohttp.ClientSession, supabase: Client, semaphore: asyncio.Semaphore) -> dict:
    """Обрабатывает один пост: классифицирует и обновляет в БД."""
    async with semaphore:
        post_id = post['id']
        competitor_name = post.get('competitor_name', 'Неизвестный')
        post_text = post.get('text', '')
        old_category = post.get('category', 'technical')

        # Анализируем пост
        analysis = await analyze_tg_post_async(competitor_name, post_text, session)
        new_category = analysis.get('category', CATEGORY_OTHER)
        new_summary = analysis.get('summary', '')
        new_tags = analysis.get('tags', [])
        is_meaningful = analysis.get('is_meaningful', False)

        # Обновляем в БД
        try:
            supabase.table('competitor_tg_posts').update({
                'category': new_category,
                'summary': new_summary,
                'tags': new_tags,
                'is_meaningful': is_meaningful
            }).eq('id', post_id).execute()

            status = "changed" if new_category != old_category else "same"
        except Exception as e:
            print(f"   DB error for post {post_id}: {e}")
            status = "error"
            new_category = old_category

        return {
            'post_id': post_id,
            'competitor': competitor_name,
            'old_category': old_category,
            'new_category': new_category,
            'status': status
        }


async def main():
    print("=" * 60)
    print("РЕКЛАССИФИКАЦИЯ TG-ПОСТОВ КОНКУРЕНТОВ")
    print("=" * 60)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if not check_env():
        return

    # Подключение к Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Подключение к Supabase...")

    # Получаем все посты с category='technical'
    print("Загрузка постов с category='technical'...")

    result = supabase.table('competitor_tg_posts') \
        .select('id, competitor_id, competitor_name, text, category, summary') \
        .eq('category', 'technical') \
        .execute()

    posts = result.data
    total_posts = len(posts)

    if total_posts == 0:
        print("Нет постов для реклассификации.")
        return

    print(f"Найдено постов: {total_posts}")
    print()

    # Статистика
    stats = {
        'total': total_posts,
        'processed': 0,
        'changed': 0,
        'same': 0,
        'errors': 0,
        'by_new_category': {}
    }

    # Обрабатываем посты
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

    async with aiohttp.ClientSession() as session:
        # Обрабатываем батчами
        batch_size = 10

        for i in range(0, total_posts, batch_size):
            batch = posts[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_posts + batch_size - 1) // batch_size

            print(f"Батч {batch_num}/{total_batches} ({len(batch)} постов)...")

            tasks = [process_post(post, session, supabase, semaphore) for post in batch]
            results = await asyncio.gather(*tasks)

            for r in results:
                stats['processed'] += 1

                if r['status'] == 'changed':
                    stats['changed'] += 1
                    print(f"   {r['competitor'][:20]}: {r['old_category']} -> {r['new_category']}")
                elif r['status'] == 'same':
                    stats['same'] += 1
                else:
                    stats['errors'] += 1

                new_cat = r['new_category']
                stats['by_new_category'][new_cat] = stats['by_new_category'].get(new_cat, 0) + 1

            # Пауза между батчами
            if i + batch_size < total_posts:
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)

    # Итоговая статистика
    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 60)
    print(f"Всего постов:      {stats['total']}")
    print(f"Обработано:        {stats['processed']}")
    print(f"Изменено:          {stats['changed']}")
    print(f"Без изменений:     {stats['same']}")
    print(f"Ошибок:            {stats['errors']}")
    print()
    print("Распределение по новым категориям:")
    for cat, count in sorted(stats['by_new_category'].items(), key=lambda x: -x[1]):
        pct = count / stats['total'] * 100
        print(f"   {cat:15} {count:4} ({pct:.1f}%)")
    print()
    print("Готово!")


if __name__ == "__main__":
    asyncio.run(main())
