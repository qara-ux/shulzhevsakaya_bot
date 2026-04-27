import logging
import json
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.marathon import MarathonState
from utils.validators import is_valid_email
from services.analytics import track_event
from services.scheduler import schedule_email_reminder, schedule_payment_reminder, cancel_reminders
from config import config
from handlers.dynamic import send_node

router = Router()

@router.message(F.successful_payment, StateFilter("*"))
async def process_successful_payment(message: Message, state: FSMContext):
    user_id = message.from_user.id
    print(f"DEBUG: Processing successful payment for {user_id}", flush=True)
    try:
        await send_node(message, "success", state)
        await state.clear()
        cancel_reminders(user_id)
        
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
        await track_event(user_id, "payment_success", message.from_user.username, amount=5000)
    except Exception as e:
        print(f"DEBUG: Success handler error: {e}", flush=True)
        await message.answer("🎉 Оплата прошла! \n\nВот ваша ссылка: https://t.me/+C-xOxlwd-MFmYjZi")

@router.callback_query(F.data == "go_to_payment")
async def send_payment_invoice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await track_event(callback.from_user.id, "click_pay", callback.from_user.username)
    await callback.answer()
    
    prices = [LabeledPrice(label="Оплата участия", amount=5000 * 100)]
    token = config.payment_token.get_secret_value()
    
    print(f"DEBUG_INVOICE_MINIMAL: user={callback.from_user.id} token_len={len(token)}", flush=True)

    try:
        # MINIMAL POSSIBLE INVOICE
        await callback.message.answer_invoice(
            title="Марафон МЕТОД",
            description="Оплата участия в марафоне",
            provider_token=token,
            currency="RUB",
            prices=prices,
            payload="marathon_payment_v2",
            start_parameter="marathon_v2"
        )
        print(f"DEBUG_INVOICE_OK: user={callback.from_user.id}", flush=True)
    except Exception as e:
        print(f"DEBUG_INVOICE_ERROR: user={callback.from_user.id} err={e}", flush=True)
    
    await state.set_state(MarathonState.waiting_for_payment)
    await track_event(callback.from_user.id, "payment_started", callback.from_user.username)

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    print(f"DEBUG_PRECHECKOUT: user={pre_checkout_query.from_user.id}", flush=True)
    try:
        await pre_checkout_query.answer(ok=True)
        print(f"DEBUG_PRECHECKOUT_OK: user={pre_checkout_query.from_user.id}", flush=True)
    except Exception as e:
        print(f"DEBUG_PRECHECKOUT_ERROR: user={pre_checkout_query.from_user.id} err={e}", flush=True)
        await pre_checkout_query.answer(ok=False, error_message="Ошибка. Попробуйте еще раз.")
