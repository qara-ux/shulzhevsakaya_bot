import logging
import json
import uuid
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from yookassa import Configuration, Payment

from states.marathon import MarathonState
from services.analytics import track_event
from services.scheduler import cancel_reminders
from config import config
from handlers.dynamic import send_node

router = Router()

# Configure YooKassa
shop_id = config.yookassa_shop_id
secret_key = config.yookassa_secret_key.get_secret_value()

if shop_id and secret_key:
    Configuration.account_id = shop_id
    Configuration.secret_key = secret_key

async def check_payment_status(payment_id: str, chat_id: int, user_id: int, bot: Bot, state: FSMContext):
    attempts = 0
    max_attempts = 240 
    while attempts < max_attempts:
        try:
            payment = Payment.find_one(payment_id)
            if payment.status == 'succeeded':
                from dashboard.api.database import SessionLocal
                from dashboard.api.models import UserRecord
                db = SessionLocal()
                try:
                    user = db.query(UserRecord).filter(UserRecord.telegram_id == user_id).first()
                    if user:
                        user.is_paid = True
                        db.commit()
                finally:
                    db.close()
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Присоединиться к марафону", url="https://t.me/+C-xOxlwd-MFmYjZi")]
                ])
                
                await bot.send_message(
                    chat_id, 
                    "🎉 Поздравляем! Оплата прошла успешно.\n\nТеперь вам открыт полный доступ к марафону «МЕТОД». Нажмите кнопку ниже, чтобы вступить в группу:",
                    reply_markup=keyboard
                )
                await track_event(user_id, "payment_success", "User", amount=5000)
                await state.clear()
                cancel_reminders(user_id)
                return True
        except: pass
        attempts += 1
        await asyncio.sleep(5)
    return False

@router.callback_query(F.data == "go_to_payment")
async def send_payment_link(callback: CallbackQuery, state: FSMContext, bot: Bot = None):
    # Ask for email first to fulfill YooKassa fiscalization requirements
    await callback.message.answer("📧 Для оформления чека, пожалуйста, введите ваш **Email**:")
    await state.set_state(MarathonState.waiting_for_email)
    await callback.answer()

@router.message(MarathonState.waiting_for_email)
async def process_email_and_create_payment(message: Message, state: FSMContext, bot: Bot):
    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.answer("⚠️ Пожалуйста, введите корректный Email (например, example@mail.ru):")
        return

    # Save email to DB
    user_id = message.from_user.id
    from dashboard.api.database import SessionLocal
    from dashboard.api.models import UserRecord
    db = SessionLocal()
    try:
        user = db.query(UserRecord).filter(UserRecord.telegram_id == user_id).first()
        if user:
            user.email = email
            db.commit()
    finally:
        db.close()

    await track_event(user_id, "email_captured", message.from_user.username, data={"email": email})
    await message.answer("⏳ Генерирую ссылку на оплату...")

    try:
        payment = Payment.create({
            "amount": {"value": "5000.00", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/method_shulzhevskoy_bot"
            },
            "capture": True,
            "description": "Марафон МЕТОД",
            "metadata": {
                "user_id": user_id,
                "bot_source": "@method_shulzhevskoy_bot"
            },
            "receipt": {
                "customer": {"email": email},
                "items": [
                    {
                        "description": "Участие в марафоне МЕТОД",
                        "quantity": "1",
                        "amount": {"value": "5000.00", "currency": "RUB"},
                        "vat_code": "1",
                        "payment_mode": "full_payment",
                        "payment_subject": "service"
                    }
                ]
            }
        }, uuid.uuid4())

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 5000₽ (СБП, Карта)", url=payment.confirmation.confirmation_url)]
        ])

        await message.answer(
            f"✅ Ссылка готова!\n\nВы указали почту: `{email}`\n\nНажмите кнопку ниже для перехода к оплате:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        asyncio.create_task(check_payment_status(payment.id, message.chat.id, user_id, bot, state))
        await state.set_state(MarathonState.waiting_for_payment)
        await track_event(user_id, "payment_started", message.from_user.username, amount=5000)

    except Exception as e:
        print(f"❌ YOOKASSA_API_ERROR: {e}", flush=True)
        await message.answer("⚠️ Ошибка создания платежа. Пожалуйста, попробуйте позже.")
