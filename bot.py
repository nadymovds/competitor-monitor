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
    candidates = [telegram_id]
    if telegram_id is not None:
        candidates.append(str(telegram_id))

    for candidate in candidates:
        try:
            result = (
                supabase.table("users")
                .select("id")
                .eq("telegram_id", candidate)
                .limit(1)
                .execute()
            )
            if result.data:
                return True
        except Exception:
            continue

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
    access_state[user.id] = "waiting_info"
    access_data[user.id] = {"telegram_username": user.username or ""}

    await update.message.reply_text(
        "👋 Привет! У вас пока нет доступа к системе мониторинга.\n\n"
        "Чтобы запросить доступ, напишите <b>кто вы</b> — имя, фамилию, отдел:",
        parse_mode="HTML",
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения в рамках флоу запроса доступа."""
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    state = access_state.get(user.id)

    if state != "waiting_info":
        return

    user_text = update.message.text.strip()

    if not user_text:
        await update.message.reply_text("Пожалуйста, напишите кто вы.")
        return

    telegram_username = access_data[user.id].get("telegram_username", "")

    # Сохраняем как ожидающий запрос
    pending_requests[str(user.id)] = {
        "user_text": user_text,
        "telegram_username": telegram_username,
    }
    del access_state[user.id]
    del access_data[user.id]

    # Уведомляем администратора
    print(f"[access_request] TELEGRAM_CHAT_ID={TELEGRAM_CHAT_ID!r}", flush=True)
    if TELEGRAM_CHAT_ID:
        username_str = f"@{telegram_username}" if telegram_username else f"ID: {user.id}"
        admin_text = (
            f"🔔 <b>Новый запрос на доступ</b>\n\n"
            f"💬 {user_text}\n\n"
            f"📨 <b>Telegram:</b> {username_str}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>"
        )
        approve_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Выдать доступ", callback_data=f"approve_access:{user.id}")
        ]])
        try:
            await context.bot.send_message(
                chat_id=int(TELEGRAM_CHAT_ID),
                text=admin_text,
                parse_mode="HTML",
                reply_markup=approve_markup,
            )
            print(f"[access_request] admin notified about user {user.id}", flush=True)
        except Exception as e:
            import traceback
            print(f"[access_request] FAILED to notify admin: {e}\n{traceback.format_exc()}", flush=True)
    else:
        print("[access_request] TELEGRAM_CHAT_ID is not set — admin not notified!", flush=True)

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
                "display_name": req["user_text"],
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
        f"✅ Доступ выдан: <b>{req['user_text']}</b>",
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
# WEBHOOK ENDPOINT
# ============================================================================

@app_flask.post("/webhook")
def webhook():
    try:
        data = request.get_json(force=True)
        update_type = list(data.keys())
        user_id = None
        if "message" in data:
            user_id = data["message"].get("from", {}).get("id")
            text = data["message"].get("text", "")
            print(f"[webhook] message from {user_id}: {text!r}", flush=True)
        elif "callback_query" in data:
            user_id = data["callback_query"].get("from", {}).get("id")
            cbd = data["callback_query"].get("data", "")
            print(f"[webhook] callback from {user_id}: {cbd!r}", flush=True)
        else:
            print(f"[webhook] update keys: {update_type}", flush=True)

        if application is None:
            print("[webhook] application not ready yet", flush=True)
            return "ok"

        update = Update.de_json(data, application.bot)
        future = asyncio.run_coroutine_threadsafe(application.process_update(update), _loop)
        future.result(timeout=60)
    except Exception as e:
        import traceback
        print(f"[webhook] error: {e}\n{traceback.format_exc()}", flush=True)
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

        asyncio.run_coroutine_threadsafe(application.initialize(), _loop).result(timeout=30)
        asyncio.run_coroutine_threadsafe(application.start(), _loop).result(timeout=30)
        print("[init_bot] application started successfully", flush=True)

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
