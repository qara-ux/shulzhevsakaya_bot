from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import datetime, timedelta

scheduler = AsyncIOScheduler()

async def send_reminder_dynamic(bot: Bot, chat_id: int, node_id: str):
    """
    Triggers a dynamic node as a reminder.
    """
    from handlers.dynamic import send_node_core
    try:
        print(f"⏰ REMINDER: Sending node '{node_id}' to {chat_id}")
        await send_node_core(bot, chat_id, node_id)
    except Exception as e:
        print(f"Failed to send reminder {node_id} to {chat_id}: {e}")

def schedule_email_reminder(bot: Bot, chat_id: int):
    job_id = f"email_rem_{chat_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        
    scheduler.add_job(
        send_reminder_dynamic,
        "date",
        run_date=datetime.now() + timedelta(minutes=15),
        args=[bot, chat_id, "rem_email"],
        id=job_id
    )

def schedule_payment_reminder(bot: Bot, chat_id: int):
    job_id = f"pay_rem_{chat_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        
    scheduler.add_job(
        send_reminder_dynamic,
        "date",
        run_date=datetime.now() + timedelta(minutes=5),
        args=[bot, chat_id, "rem_pay"],
        id=job_id
    )

def cancel_reminders(chat_id: int):
    for prefix in ["email_rem_", "pay_rem_"]:
        job_id = f"{prefix}{chat_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
