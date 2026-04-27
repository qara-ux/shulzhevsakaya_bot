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
    logging.info(f"✅ Successful payment received from {user_id}")
    
    try:
        # 1. Immediate Success Response
        await send_node(message, "success", state)
        await state.clear()
        cancel_reminders(user_id)
        
        # 2. Update DB
        from dashboard.api.database import SessionLocal
        from dashboard.api.models import UserRecord
        db = SessionLocal()
        email = None
        try:
            email = message.successful_payment.order_info.email if message.successful_payment.order_info else None
            user = db.query(UserRecord).filter(UserRecord.telegram_id == user_id).first()
            if user:
                user.is_paid = True
                if email: user.email = email
                db.commit()
            logging.info(f"💾 Database updated for user {user_id}")
        except Exception as db_err:
            logging.error(f"❌ DB update error: {db_err}")
        finally:
            db.close()

        # 3. Analytics & Email Receipt
        await track_event(user_id, "payment_success", message.from_user.username, amount=5000, email=email)
        
        if email:
            from services.email_service import send_receipt_email
            await send_receipt_email(email, 5000, message.from_user.username or "Участник")
            
    except Exception as e:
        logging.error(f"🚨 Error in success payment handler: {e}")
        await message.answer("🎉 Оплата прошла! Ссылка на группу: https://t.me/+C-xOxlwd-MFmYjZi")

@router.callback_query(F.data == "go_to_payment")
async def send_payment_invoice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await track_event(callback.from_user.id, "click_pay", callback.from_user.username)
    await callback.answer()
    
    prices = [LabeledPrice(label="Участие в марафоне «МЕТОД»", amount=5000 * 100)]
    token = config.payment_token.get_secret_value()
    
    # 54-FZ Compliance: Receipt data for YooKassa
    provider_data = {
        "receipt": {
            "items": [
                {
                    "description": "Участие в марафоне «МЕТОД»",
                    "quantity": "1.00",
                    "amount": {
                        "value": "5000.00",
                        "currency": "RUB"
                    },
                    "vat_code": 1 # No VAT
                }
            ]
        }
    }

    try:
        logging.info(f"📤 Sending live invoice to {callback.from_user.id}")
        await callback.message.answer_invoice(
            title="Марафон «МЕТОД»",
            description="Полный доступ к весеннему марафону трансформации (4 недели)",
            provider_token=token,
            currency="rub",
            prices=prices,
            payload="marathon_payment_final",
            start_parameter="marathon_final",
            provider_data=json.dumps(provider_data),
            need_email=True,
            send_email_to_provider=True
        )
    except Exception as e:
        logging.error(f"❌ Invoice sending failed: {e}")
    
    await state.set_state(MarathonState.waiting_for_payment)
    await track_event(callback.from_user.id, "payment_started", callback.from_user.username)
    schedule_payment_reminder(bot, callback.from_user.id)

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    logging.info(f"💳 PreCheckoutQuery from {pre_checkout_query.from_user.id}")
    try:
        await pre_checkout_query.answer(ok=True)
    except Exception as e:
        logging.error(f"❌ PreCheckout error: {e}")
        await pre_checkout_query.answer(ok=False, error_message="Ошибка на стороне сервера. Попробуйте еще раз через минуту.")
