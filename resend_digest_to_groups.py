"""
Одноразовый скрипт: переотправить последний дайджест новостей
только в групповые чаты — без инлайн-кнопки, со ссылкой на бот.

Запуск:
    python resend_digest_to_groups.py
"""

import os
import requests
from datetime import datetime

from news_monitor import (
    generate_news_digest_pdf,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_GROUP_CHAT_IDS,
    BOT_URL,
    supabase,
)

# 1. Последний дайджест
print("📥 Загружаю последний дайджест...")
digest = (
    supabase.table("news_digests")
    .select("*")
    .order("digest_date", desc=True)
    .limit(1)
    .single()
    .execute()
    .data
)
print(f"   Дайджест: {digest['digest_date']}, постов: {digest['posts_count']}, id={digest['id']}")

# 2. Посты с категориями и цветами
print("📥 Загружаю посты дайджеста...")
rows = (
    supabase.table("news_digest_posts")
    .select(
        "news_posts("
        "id, title, content_text, summary, post_url, post_date, views_count, source_type, "
        "news_channels(title, username), "
        "news_post_categories(confidence, news_categories(id, name, color))"
        ")"
    )
    .eq("digest_id", digest["id"])
    .order("rank_in_category")
    .execute()
    .data
)

# 3. Преобразуем в формат, ожидаемый generate_news_digest_pdf()
posts_flat = []
channels_seen = set()
for row in rows:
    post = row.get("news_posts")
    if not post:
        continue

    channel_info = post.get("news_channels") or {}
    channel_title = channel_info.get("title") or channel_info.get("username", "")
    if channel_title:
        channels_seen.add(channel_title)

    category_tags = [
        {
            "name": pc["news_categories"]["name"],
            "color": pc["news_categories"].get("color", "#888888"),
        }
        for pc in (post.get("news_post_categories") or [])
        if pc.get("news_categories")
    ]
    if not category_tags:
        category_tags = [{"name": "Прочее", "color": "#888888"}]

    posts_flat.append(
        {
            "title": post.get("title", ""),
            "summary": post.get("summary", ""),
            "content_text": post.get("content_text", ""),
            "post_url": post.get("post_url", ""),
            "channel_title": channel_title,
            "post_date": post.get("post_date", ""),
            "views_count": post.get("views_count", 0),
            "source_type": post.get("source_type", "telegram"),
            "category_tags": category_tags,
        }
    )

print(f"   Загружено постов: {len(posts_flat)}")

# 4. Генерируем PDF
print("📄 Генерирую PDF...")
period_start = datetime.fromisoformat(digest["period_start"])
period_end = datetime.fromisoformat(digest["period_end"])

pdf_path = generate_news_digest_pdf(
    digest_date=digest["digest_date"],
    period_start=period_start,
    period_end=period_end,
    posts=posts_flat,
    channels_count=len(channels_seen),
)
print(f"   PDF: {pdf_path}")

# 5. Caption для группового чата (без инлайн-кнопки)
period_str = f"{period_start.strftime('%d.%m.%Y')} — {period_end.strftime('%d.%m.%Y')}"
caption = (
    f"📊 <b>Мониторинг новостей завершён</b>\n\n"
    f"📅 Период: {period_str}\n"
    f"📰 Постов в дайджесте: <b>{digest['posts_count']}</b>\n\n"
    f"📎 Подробный дайджест во вложении\n\n"
    f'📲 <a href="{BOT_URL}">Открыть подробности в боте</a>'
)

# 6. Отправляем только в группы
if not TELEGRAM_GROUP_CHAT_IDS:
    print("⚠️ TELEGRAM_GROUP_CHAT_ID не задан — отправлять некуда.")
else:
    for chat_id in TELEGRAM_GROUP_CHAT_IDS:
        print(f"📤 Отправляю в группу {chat_id}...")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(pdf_path, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"document": f},
                timeout=60,
            )
        if resp.ok and resp.json().get("ok"):
            print(f"   ✅ Отправлено")
        else:
            print(f"   ❌ Ошибка: {resp.text}")

# 7. Удаляем PDF
try:
    os.remove(pdf_path)
    print(f"🗑️ PDF удалён: {pdf_path}")
except OSError:
    pass

print("✅ Готово")
