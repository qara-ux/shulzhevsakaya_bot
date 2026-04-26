import os
import sys
import asyncio
import logging
import signal
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
        try:
            # Try to find a way to reply to the user
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
        except Exception as e:
            logging.error(f"Failed to send error message: {e}")

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
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
