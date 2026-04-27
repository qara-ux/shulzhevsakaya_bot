import os
import sys
import asyncio
import logging
import signal
import sys

# HIGH VISIBILITY STARTUP LOG
print("\n" + "="*50, flush=True)
print("🚀!!! REGINA BOT IS STARTING UP ON RAILWAY !!!🚀", flush=True)
print("="*50 + "\n", flush=True)

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage

PID_FILE = "bot.pid"

def check_single_instance():
    import subprocess
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = f.read().strip()
            
            # Deep check: verify if PID exists AND it is actually main.py
            result = subprocess.run(['ps', '-ww', '-p', pid, '-o', 'command='], capture_output=True, text=True)
            if "main.py" in result.stdout:
                print(f"CRITICAL: Another bot instance is already running (PID: {pid}). Aborting.")
                sys.exit(1)
        except Exception:
            pass
    
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def cleanup_pid(signum, frame):
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    sys.exit(0)

# Handle graceful shutdown
signal.signal(signal.SIGINT, cleanup_pid)
signal.signal(signal.SIGTERM, cleanup_pid)

check_single_instance()

# Configure logging

from config import config
from handlers import start, dynamic, payment, faq
from services.scheduler import scheduler

# Initialize database tables
try:
    from dashboard.api.database import engine, Base, SessionLocal
    from dashboard.api.models import AnalyticsEvent, UserRecord, ScheduledBroadcast, BotNode
    Base.metadata.create_all(bind=engine)
    logging.info("Database tables initialized.")
    
    # Check if we need to seed the initial nodes
    db = SessionLocal()
    node_count = db.query(BotNode).count()
    first_node = db.query(BotNode).first()
    
    # Seed if empty or if it only contains the 'placeholder' welcome message
    if node_count == 0 or (node_count == 1 and "Бот успешно запущен на Railway" in first_node.content):
        logging.info("Seeding full funnel structure...")
        if node_count > 0:
            db.query(BotNode).delete() # Clear the placeholder
        
        nodes_data = [
            {
                "id": "entry",
                "title": "0 ENTRY (вход)",
                "content": "🌸 Весенний марафон «МЕТОД»\n\nСтарт — 11 мая\nФормат — онлайн\n4 недели трансформации\n\nГотова присоединиться?",
                "buttons": [{"text": "✅ Да, готова!", "next_node": "intent"}, {"text": "🔥 Что я получу?", "next_node": "value"}],
                "is_start_node": True, "x": 115, "y": 323
            },
            {
                "id": "value",
                "title": "0.1 VALUE BLOCK",
                "content": "Ты получаешь 👇\n\n🌿 4 недели тренировок\nПрокачка всего тела, укрепление, коррекция фигуры\nОсобый упор на ягодичные мышцы\n\n🎥 Удобный формат\nПросто включай видео и повторяй за тренером\n\n📅 5 отдельных каналов:\n1️⃣ Неделя 1\n2️⃣ Неделя 2\n3️⃣ Неделя 3\n4️⃣ Неделя 4\n\n🍴 Питание\nПолноценные рационы на каждый день\n\nГотова присоединиться?",
                "buttons": [{"text": "✅ Да, готова", "next_node": "intent"}],
                "is_start_node": False, "x": 463, "y": 140
            },
            {
                "id": "intent",
                "title": "1. INTENT CONFIRMATION",
                "content": "Отлично 👇\n\nСтоимость участия:\n5000₽\n\nДоступ открывается сразу после оплаты",
                "buttons": [{"text": "💳 Перейти к оплате", "next_node": "pay"}],
                "is_start_node": False, "x": 843, "y": 301
            },
            {
                "id": "contact",
                "title": "2. PAYMENT INTENT",
                "content": "Чтобы подготовить чек на оплату, укажите вашу почту \n\nВведите email 👇",
                "buttons": [],
                "is_start_node": False, "x": 1151, "y": 534
            },
            {
                "id": "checkout",
                "title": "3. CHECKOUT",
                "content": "Остался последний шаг 🙌\n\nПереходи к оплате 👇",
                "buttons": [{"text": "🔗 Оплатить участие (5000₽)", "next_node": "success"}],
                "is_start_node": False, "x": 1497, "y": 299
            },
            {
                "id": "success",
                "title": "4. SUCCESS",
                "content": "Поздравляю! 💥\n\nОплата прошла успешно, теперь переходи в закрытую группу и ожидай начало марафона",
                "buttons": [{"text": "Присоединиться 🚀", "url": "https://t.me/+C-xOxlwd-MFmYjZi"}],
                "is_start_node": False, "x": 1897, "y": 298
            },
            {
                "id": "rem_email",
                "title": "Дожим: Почта",
                "content": "Ты не завершила регистрацию 👇\nЗакрепить за тобой место?",
                "buttons": [{"text": "💳 Перейти к оплате", "next_node": "pay"}],
                "is_start_node": False, "x": 0, "y": 0
            },
            {
                "id": "rem_pay",
                "title": "Дожим: Оплата",
                "content": "Ты почти в марафоне 👇\nМеста ограничены. Попробуем еще раз?",
                "buttons": [{"text": "💳 Перейти к оплате", "next_node": "pay"}],
                "is_start_node": False, "x": 0, "y": 0
            }
        ]
        for n_data in nodes_data:
            node = BotNode(**n_data)
            db.add(node)
        db.commit()
    db.close()
except Exception as e:
    logging.error(f"Failed to initialize database: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

async def main():
    # Initialize bot and dispatcher
    bot = Bot(token=config.bot_token.get_secret_value())
    dp = Dispatcher(storage=MemoryStorage())

    # Include routers - Order Matters!
    # The start router MUST be first to override any stuck FSM states.
    dp.include_router(start.router)
    dp.include_router(payment.router)
    dp.include_router(faq.router)
    dp.include_router(dynamic.router)

    # Global error handler
    @dp.errors()
    async def error_handler(event: types.ErrorEvent):
        logging.error(f"⚠️ GLOBAL ERROR: {event.exception}", exc_info=True)
        
        # 1. Notify the user
        try:
            msg = None
            if event.update.message:
                msg = event.update.message
            elif event.update.callback_query:
                msg = event.update.callback_query.message
            
            if msg:
                await msg.answer(
                    "Извини, произошла небольшая техническая ошибка 🍫\n"
                    "Мы уже чиним её! Попробуй нажать /start через минуту."
                )
        except: pass

        # 2. Notify the Admin with traceback
        try:
            import traceback
            tb_str = traceback.format_exc()
            error_msg = f"❌ <b>БОТ УПАЛ!</b>\n\n<b>Ошибка:</b> {event.exception}\n\n<code>{tb_str[:3000]}</code>"
            await bot.send_message(config.admin_id, error_msg, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Could not send error to admin: {e}")

    # Start scheduler
    scheduler.start()

    # Start polling
    logging.info("Bot started...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    # Prevent local runs from conflicting with Railway unless explicitly allowed for testing
    is_local = not os.getenv("RAILWAY_ENVIRONMENT") and not os.getenv("PORT")
    allow_test = os.getenv("LOCAL_TEST", "").lower() == "true"

    if is_local and not allow_test:
        print("\n" + "!"*60)
        print("⚠️  LOCAL RUN DETECTED: Bot polling is DISABLED locally.")
        print("To run locally for testing, set LOCAL_TEST=true in your .env")
        print("and use a SEPARATE bot token to avoid conflicts.")
        print("!"*60 + "\n")
        sys.exit(0)

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
