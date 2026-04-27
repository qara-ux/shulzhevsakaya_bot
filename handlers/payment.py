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
else:
    print("⚠️ WARNING: YooKassa keys are MISSING in config!", flush=True)

async def check_payment_status(payment_id: str, chat_id: int, user_id: int, bot: Bot, state: FSMContext):
    attempts = 0
    max_attempts = 240 
    while attempts < max_attempts:
        try:
            payment = Payment.find_one(payment_id)
            if payment.status == 'succeeded':
                print(f"✅ POLLING_SUCCESS: User {user_id} paid {payment_id}", flush=True)
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
                
                await bot.send_message(
                    chat_id, 
                    "🎉 **Поздравляем! Оплата прошла успешно.**\n\nТеперь вам открыт полный доступ к марафону «МЕТОД».\n\n👉 Ссылка на закрытую группу: https://t.me/+C-xOxlwd-MFmYjZi",
                    parse_mode="Markdown"
                )
                await track_event(user_id, "payment_success", "User", amount=5000)
                await state.clear()
                cancel_reminders(user_id)
                return True
            if payment.status == 'canceled': return False
        except Exception as e:
            print(f"⚠️ POLLING_ERROR: {e}", flush=True)
        attempts += 1
        await asyncio.sleep(5)
    return False

@router.callback_query(F.data == "go_to_payment")
async def send_payment_link(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await track_event(callback.from_user.id, "click_pay", callback.from_user.username)
    await callback.answer()
    
    if not shop_id or not secret_key:
        await callback.message.answer("⚠️ Сервис оплаты еще не настроен. Проверьте переменные окружения.")
        return

    try:
        payment = Payment.create({
            "amount": {"value": "5000.00", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/method_shulzhevskoy_bot"
            },
            "capture": True,
            "description": "Оплата участия в марафоне «МЕТОД»",
            "metadata": {
                "user_id": callback.from_user.id,
                "bot_source": "@method_shulzhevskoy_bot"
            }
        }, uuid.uuid4())

        payment_url = payment.confirmation.confirmation_url
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате (5000₽)", url=payment_url)],
            [InlineKeyboardButton(text="❓ Помощь / Поддержка", callback_data="node_faq")]
        ])

        await callback.message.answer(
            "🚀 **Почти готово!**\n\nНажмите на кнопку ниже, чтобы перейти на страницу оплаты ЮKassa.\n\nТам вы сможете выбрать **СБП**, карту или другой удобный способ.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        asyncio.create_task(check_payment_status(payment.id, callback.message.chat.id, callback.from_user.id, bot, state))
        await state.set_state(MarathonState.waiting_for_payment)
        await track_event(callback.from_user.id, "payment_started", callback.from_user.username)

    except Exception as e:
        print(f"❌ YOOKASSA_API_ERROR: type={type(e)} msg={str(e)}", flush=True)
        await callback.message.answer("⚠️ Ошибка создания платежа. Попробуйте еще раз или напишите нам.")

@router.message(F.successful_payment, StateFilter("*"))
async def process_successful_payment(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await send_node(message, "success", state)
    await state.clear()
    cancel_reminders(user_id)
