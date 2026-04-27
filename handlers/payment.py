import logging
import json
import uuid
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
Configuration.account_id = config.yookassa_shop_id
Configuration.secret_key = config.yookassa_secret_key.get_secret_value()

@router.callback_query(F.data == "go_to_payment")
async def send_payment_link(callback: CallbackQuery, state: FSMContext):
    await track_event(callback.from_user.id, "click_pay", callback.from_user.username)
    await callback.answer()
    
    try:
        # Create payment via YooKassa API
        payment = Payment.create({
            "amount": {
                "value": "5000.00",
                "currency": "RUB"
            },
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
            "🚀 **Почти готово!**\n\nНажмите на кнопку ниже, чтобы перейти на защищенную страницу оплаты ЮKassa.\n\nТам вы сможете выбрать любой удобный способ: **СБП**, карты, SberPay или T-Pay.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        print(f"✅ PAYMENT_LINK_CREATED: user={callback.from_user.id} url={payment_url[:30]}...", flush=True)
        await state.set_state(MarathonState.waiting_for_payment)
        await track_event(callback.from_user.id, "payment_started", callback.from_user.username)

    except Exception as e:
        print(f"❌ YOOKASSA_API_ERROR: {e}", flush=True)
        await callback.message.answer("⚠️ К сожалению, сейчас создание платежа недоступно. Попробуйте через 5 минут или обратитесь в поддержку.")

# We can keep the successful_payment handler for legacy, but webhooks will be primary
@router.message(F.successful_payment, StateFilter("*"))
async def process_successful_payment(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await send_node(message, "success", state)
    await state.clear()
    cancel_reminders(user_id)
