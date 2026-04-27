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
    print(f"✅ SUCCESS_PAYMENT: {user_id}", flush=True)
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
        print(f"🚨 SUCCESS_ERROR: {e}", flush=True)
        await message.answer("🎉 Оплата прошла! Ссылка: https://t.me/+C-xOxlwd-MFmYjZi")

@router.callback_query(F.data == "go_to_payment")
async def send_payment_invoice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await track_event(callback.from_user.id, "click_pay", callback.from_user.username)
    await callback.answer()
    
    prices = [LabeledPrice(label="Участие в марафоне «МЕТОД»", amount=5000 * 100)]
    token = config.payment_token.get_secret_value()
    
    # EXACT provider_data structure from YooKassa support
    provider_data = {
        "receipt": {
            "items": [
                {
                    "description": "Участие в марафоне «МЕТОД»",
                    "quantity": 1,
                    "amount": {
                        "value": "5000.00",
                        "currency": "RUB"
                    },
                    "vat_code": 1, # 1=No VAT, 4=20% VAT. Using 1 as baseline.
                    "payment_mode": "full_payment",
                    "payment_subject": "service"
                }
            ],
            "tax_system_code": 1 # 1=OSN, 2=USN. Using 1 as per example.
        }
    }

    print(f"📤 SENDING_EXACT_INVOICE: user={callback.from_user.id}", flush=True)

    try:
        await bot.send_invoice(
            chat_id=callback.message.chat.id,
            title="Марафон «МЕТОД»",
            description="Полный доступ к 4 неделям марафона",
            provider_token=token,
            currency="RUB",
            prices=prices,
            payload=f"marathon_payment_{callback.from_user.id}",
            start_parameter="marathon_reg",
            provider_data=json.dumps(provider_data),
            need_email=True,
            send_email_to_provider=True
        )
        print(f"✅ INVOICE_SENT_OK", flush=True)
    except Exception as e:
        print(f"❌ INVOICE_SEND_ERROR: {e}", flush=True)
    
    await state.set_state(MarathonState.waiting_for_payment)
    await track_event(callback.from_user.id, "payment_started", callback.from_user.username)

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    print(f"💳 PRE_CHECKOUT_RECEIVED: {pre_checkout_query.from_user.id}", flush=True)
    try:
        await pre_checkout_query.answer(ok=True)
        print(f"✅ PRE_CHECKOUT_ANSWERED_OK", flush=True)
    except Exception as e:
        print(f"❌ PRE_CHECKOUT_ERROR: {e}", flush=True)
        await pre_checkout_query.answer(ok=False, error_message="Ошибка. Попробуйте еще раз.")
