import asyncio
import os
import threading
from datetime import datetime

from flask import Flask, request
from supabase import create_client, Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters, ContextTypes,
)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # https://your-app.onrender.com
BOT_URL = os.environ.get("BOT_URL", "https://t.me/skai_compit_bot")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")  # GitHub Pages URL мини-приложения
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # ID чата администратора

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app_flask = Flask(__name__)
application: Application = None

# Персистентный event loop в background-треде
_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, daemon=True).start()

# Состояния для флоу запроса доступа (глобальные словари — надёжнее ConversationHandler в webhook-режиме)
# access_state: {telegram_id: 'waiting_name' | 'waiting_dept'}
access_state: dict = {}
# access_data: {telegram_id: {display_name, telegram_username}}
access_data: dict = {}
# pending_requests: {str(telegram_id): {display_name, department, telegram_username}} — ожидают апрува
pending_requests: dict = {}

# ============================================================================
# АВТОРИЗАЦИЯ
# ============================================================================

def is_user_allowed(telegram_id: int) -> bool:
    """Проверяет, есть ли пользователь в таблице users (как в мини-апп)."""
    try:
        result = (
            supabase.table("users")
            .select("id")
            .eq("telegram_id", telegram_id)
            .single()
            .execute()
        )
        return result.data is not None
    except Exception:
        return False


# ============================================================================
# ЗАПРОС ДОСТУПА
# ============================================================================

def _make_webapp_button() -> InlineKeyboardMarkup:
    """Инлайн-кнопка для открытия мини-приложения."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📱 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик /start. Для незарегистрированных запускает флоу запроса доступа."""
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    print(f"[start] user={user.id} (@{user.username})", flush=True)

    if is_user_allowed(user.id):
        text = "👋 Вы уже в системе!"
        if WEBAPP_URL:
            await update.message.reply_text(text, reply_markup=_make_webapp_button())
        else:
            await update.message.reply_text(text)
        return

    # Сбрасываем предыдущее состояние (если было)
    access_state[user.id] = "waiting_name"
    access_data[user.id] = {"telegram_username": user.username or ""}

    await update.message.reply_text(
        "👋 Привет! У вас пока нет доступа к системе мониторинга.\n\n"
        "Чтобы запросить доступ, пришлите ваши <b>имя и фамилию</b>:",
        parse_mode="HTML",
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения в рамках флоу запроса доступа."""
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    state = access_state.get(user.id)

    if state == "waiting_name":
        access_data[user.id]["display_name"] = update.message.text.strip()
        access_state[user.id] = "waiting_dept"
        await update.message.reply_text(
            "Отлично! Теперь укажите ваш <b>отдел</b>:", parse_mode="HTML"
        )

    elif state == "waiting_dept":
        display_name = access_data[user.id].get("display_name", "")
        department = update.message.text.strip()
        telegram_username = access_data[user.id].get("telegram_username", "")

        # Сохраняем как ожидающий запрос
        pending_requests[str(user.id)] = {
            "display_name": display_name,
            "department": department,
            "telegram_username": telegram_username,
        }
        del access_state[user.id]
        del access_data[user.id]

        # Уведомляем администратора
        if TELEGRAM_CHAT_ID:
            username_str = f"@{telegram_username}" if telegram_username else f"ID: {user.id}"
            admin_text = (
                f"🔔 <b>Новый запрос на доступ</b>\n\n"
                f"👤 <b>Имя:</b> {display_name}\n"
                f"🏢 <b>Отдел:</b> {department}\n"
                f"📨 <b>Telegram:</b> {username_str}\n"
                f"🆔 <b>ID:</b> <code>{user.id}</code>"
            )
            approve_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Выдать доступ", callback_data=f"approve_access:{user.id}")
            ]])
            try:
                await context.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=admin_text,
                    parse_mode="HTML",
                    reply_markup=approve_markup,
                )
                print(f"[access_request] admin notified about {user.id}", flush=True)
            except Exception as e:
                print(f"[access_request] failed to notify admin: {e}", flush=True)

        await update.message.reply_text(
            "✅ Запрос отправлен! Ожидайте подтверждения от администратора."
        )


async def handle_approve_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Администратор нажал «Выдать доступ» — добавляем юзера в БД и уведомляем его."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    telegram_id = int(query.data.split(":")[1])
    req = pending_requests.pop(str(telegram_id), None)

    if req is None:
        await query.edit_message_text("⚠️ Запрос не найден (возможно, бот перезапускался).")
        return

    # Записываем пользователя в БД
    try:
        supabase.table("users").upsert(
            {
                "telegram_id": telegram_id,
                "telegram_username": req["telegram_username"],
                "display_name": req["display_name"],
                "role": "viewer",
                "last_seen_at": datetime.utcnow().isoformat(),
            },
            on_conflict="telegram_id",
        ).execute()
    except Exception as e:
        print(f"[approve_access] DB error: {e}", flush=True)
        await query.edit_message_text(f"❌ Ошибка при записи в БД: {e}")
        return

    # Обновляем сообщение у администратора
    await query.edit_message_text(
        f"✅ Доступ выдан: <b>{req['display_name']}</b> ({req['department']})",
        parse_mode="HTML",
    )

    # Уведомляем нового пользователя
    success_text = (
        "✅ <b>Доступ получен!</b>\n\n"
        "Теперь вы будете получать уведомления о новостях рынка и конкурентов."
    )
    try:
        if WEBAPP_URL:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=success_text,
                parse_mode="HTML",
                reply_markup=_make_webapp_button(),
            )
        else:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=success_text,
                parse_mode="HTML",
            )
    except Exception as e:
        print(f"[approve_access] failed to notify user {telegram_id}: {e}", flush=True)


# ============================================================================
# HANDLER
# ============================================================================

def _is_group_chat(chat_id) -> bool:
    try:
        return int(chat_id) < 0
    except (ValueError, TypeError):
        return False


async def handle_show_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if not is_user_allowed(query.from_user.id):
        bot_link = f" {BOT_URL}" if BOT_URL else ""
        try:
            await query.answer(f"🔒 У вас нет доступа к боту.{bot_link}", show_alert=True)
        except Exception:
            pass
        return

    try:
        await query.answer()
    except Exception:
        pass  # callback query истёк — не критично

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
    batch = posts[offset: offset + 1]

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
                f"➡️ Следующая ({shown_end + 1}/{total})",
                callback_data=f"show_posts:{digest_id}:{shown_end}"
            )
        ]])
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"📰 {shown_end} из {total}",
            reply_markup=nav_markup
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"✅ Все {total} постов за неделю показаны\n💡 Больше новостей и фильтры — в мини-апп"
        )


async def handle_show_tg_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if not is_user_allowed(query.from_user.id):
        bot_link = f" {BOT_URL}" if BOT_URL else ""
        try:
            await query.answer(f"🔒 У вас нет доступа к боту.{bot_link}", show_alert=True)
        except Exception:
            pass
        return

    try:
        await query.answer()
    except Exception:
        pass

    parts = query.data.split(":")
    report_id = parts[1]
    offset = int(parts[2])

    print(f"[tg_posts] report_id={report_id} offset={offset}", flush=True)

    result = (
        supabase.table("competitor_tg_posts")
        .select(
            "id, channel_username, content_text, summary, title, post_url, "
            "post_date, views_count, category, tags, "
            "competitors(name)"
        )
        .eq("report_id", report_id)
        .eq("is_processed", True)
        .order("post_date", desc=False)
        .execute()
    )

    print(f"[tg_posts] found {len(result.data) if result.data else 0} posts", flush=True)

    if not result.data:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Данные по TG-постам недоступны"
        )
        return

    posts = result.data
    total = len(posts)
    batch = posts[offset: offset + 1]

    for post in batch:
        text = format_tg_post_card(post)
        reply_markup = None
        if post.get("post_url"):
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Открыть в Telegram", url=post["post_url"])
            ]])
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        await asyncio.sleep(0.05)

    shown_end = offset + len(batch)
    if shown_end < total:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        nav_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"➡️ Следующий ({shown_end + 1}/{total})",
                callback_data=f"show_tg_posts:{report_id}:{shown_end}"
            )
        ]])
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"📱 {shown_end} из {total}",
            reply_markup=nav_markup
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"✅ Все {total} TG-постов показаны"
        )


def format_tg_post_card(post: dict) -> str:
    competitor = post.get("competitors") or {}
    competitor_name = competitor.get("name") or "Конкурент"
    channel = post.get("channel_username") or ""
    channel_str = f"@{channel}" if channel else ""

    body = post.get("content_text") or post.get("summary") or post.get("title") or ""
    if len(body) > 3800:
        body = body[:3800] + "…"

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

    views_str = ""
    views_count = post.get("views_count")
    if views_count:
        views_str = f"\n👁 {views_count:,}".replace(",", " ") + " просмотров"

    category_icons = {
        "products": "🏷️ Продукты",
        "prices": "💰 Цены/акции",
        "news": "📰 Новости",
        "promotion": "📣 Продвижение",
    }
    category = post.get("category") or ""
    category_str = f"\n🔖 {category_icons[category]}" if category in category_icons else ""

    return f"📱 <b>{competitor_name}</b> {channel_str}\n\n{body}{date_str}{views_str}{category_str}"


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
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        future = asyncio.run_coroutine_threadsafe(application.process_update(update), _loop)
        future.result(timeout=60)
    except Exception as e:
        print(f"[webhook] error: {e}", flush=True)
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

def _init_bot():
    """Инициализация бота в фоне — не блокирует старт Flask."""
    global application
    try:
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(CallbackQueryHandler(handle_approve_access, pattern=r"^approve_access:"))
        application.add_handler(CallbackQueryHandler(handle_show_posts, pattern=r"^show_posts:"))
        application.add_handler(CallbackQueryHandler(handle_show_tg_posts, pattern=r"^show_tg_posts:"))

        asyncio.run_coroutine_threadsafe(application.initialize(), _loop).result(timeout=30)

        import requests as req
        webhook_endpoint = f"{WEBHOOK_URL}/webhook"
        resp = req.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
            json={"url": webhook_endpoint, "allowed_updates": ["message", "callback_query"]},
            timeout=15
        )
        print(f"Webhook set: {resp.json()}", flush=True)
    except Exception as e:
        print(f"[init_bot] error: {e}", flush=True)


def main():
    # Запускаем Flask сразу — Render требует биндинг порта в течение 5 минут
    threading.Thread(target=_init_bot, daemon=True).start()

    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Flask on port {port}...", flush=True)
    app_flask.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
