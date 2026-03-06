import asyncio
import os
import threading

from flask import Flask, request
from supabase import create_client, Client
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://your-app.onrender.com

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app_flask = Flask(__name__)
application: Application = None

# Персистентный event loop в background-треде
_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True).start()

# ============================================================================
# HANDLER
# ============================================================================

async def handle_show_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    digest_id = int(parts[1])
    offset = int(parts[2])

    # Загрузить посты из Supabase
    result = (
        supabase.table("news_digest_posts")
        .select(
            "news_posts("
            "id, title, content_text, summary, post_url, post_date, views_count, source_type, "
            "news_channels(title, username), "
            "news_post_categories(news_categories(name))"
            ")"
        )
        .eq("digest_id", digest_id)
        .order("rank_in_category")
        .execute()
    )

    if not result.data:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Данные дайджеста недоступны"
        )
        return

    posts = [row["news_posts"] for row in result.data if row.get("news_posts")]
    total = len(posts)
    batch = posts[offset: offset + 10]

    for post in batch:
        text = format_post_card(post)
        reply_markup = None
        if post.get("post_url"):
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Открыть источник", url=post["post_url"])
            ]])
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        await asyncio.sleep(0.05)

    # Навигационное сообщение
    shown_end = offset + len(batch)
    if shown_end < total:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        nav_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "📋 Показать ещё →",
                callback_data=f"show_posts:{digest_id}:{shown_end}"
            )
        ]])
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"📰 Показано {offset + 1}–{shown_end} из {total} постов",
            reply_markup=nav_markup
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"✅ Все {total} постов за неделю показаны\n💡 Больше новостей и фильтры — в мини-апп"
        )


def format_post_card(post: dict) -> str:
    source_type = post.get("source_type", "")
    icon = "📱" if source_type == "telegram" else "🌐"

    channel = post.get("news_channels") or {}
    channel_title = channel.get("title") or channel.get("username") or "Источник"

    # Текст поста: content_text → summary → title
    body = post.get("content_text") or post.get("summary") or post.get("title") or ""
    if len(body) > 3800:
        body = body[:3800] + "…"

    # Дата
    post_date = post.get("post_date")
    date_str = ""
    if post_date:
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(post_date[:10])
            months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                      "июля", "августа", "сентября", "октября", "ноября", "декабря"]
            date_str = f"\n📅 {dt.day} {months[dt.month - 1]} {dt.year}"
        except Exception:
            date_str = f"\n📅 {post_date[:10]}"

    # Просмотры (только для Telegram)
    views_str = ""
    views_count = post.get("views_count")
    if source_type == "telegram" and views_count:
        views_str = f"\n👁 {views_count:,}".replace(",", " ") + " просмотров"

    # Категории (теги)
    tags_str = ""
    raw_cats = post.get("news_post_categories") or []
    cat_names = []
    for item in raw_cats:
        cat = item.get("news_categories") or {}
        name = cat.get("name")
        if name:
            cat_names.append(name)
    if cat_names:
        tags_str = "\n🏷 " + " · ".join(cat_names)

    return f"{icon} <b>{channel_title}</b>\n\n{body}{date_str}{views_str}{tags_str}"


# ============================================================================
# WEBHOOK ENDPOINT
# ============================================================================

@app_flask.post("/webhook")
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    future = asyncio.run_coroutine_threadsafe(application.process_update(update), _loop)
    future.result(timeout=60)
    return "ok"

@app_flask.get("/")
def health():
    return "ok"

@app_flask.get("/webhook-info")
def webhook_info():
    import requests as req
    resp = req.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo")
    return resp.json()


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

def main():
    global application

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(handle_show_posts, pattern=r"^show_posts:"))

    # Инициализировать application в том же event loop
    asyncio.run_coroutine_threadsafe(application.initialize(), _loop).result()

    # Установить webhook при старте
    import requests as req
    webhook_endpoint = f"{WEBHOOK_URL}/webhook"
    resp = req.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
        json={"url": webhook_endpoint, "allowed_updates": ["message", "callback_query"]}
    )
    print(f"Webhook set: {resp.json()}")

    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Flask on port {port}...")
    app_flask.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
