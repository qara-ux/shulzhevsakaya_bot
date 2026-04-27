import logging
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
        email = None
        try:
            email = message.successful_payment.order_info.email if message.successful_payment.order_info else None
            user = db.query(UserRecord).filter(UserRecord.telegram_id == user_id).first()
            if user:
                user.is_paid = True
                if email: user.email = email
                db.commit()
        except Exception as db_err:
            print(f"DEBUG: DB error: {db_err}", flush=True)
        finally:
            db.close()

        await track_event(user_id, "payment_success", message.from_user.username, amount=5000, email=email)
        
        if email:
            from services.email_service import send_receipt_email
            await send_receipt_email(email, 5000, message.from_user.username or "Участник")
            
    except Exception as e:
        print(f"DEBUG: Critical error in success handler: {e}", flush=True)
        await message.answer("🎉 Оплата прошла! \n\nВот ваша ссылка: https://t.me/+C-xOxlwd-MFmYjZi")

@router.message(F.text, StateFilter(MarathonState.waiting_for_email))
async def process_email_legacy(message: Message, state: FSMContext, bot: Bot):
    email = message.text.strip()
    if not is_valid_email(email):
        await message.answer("❌ Некорректный email. Попробуйте еще раз.")
        return

    from dashboard.api.database import SessionLocal
    from dashboard.api.models import UserRecord
    db = SessionLocal()
    user = db.query(UserRecord).filter(UserRecord.telegram_id == message.from_user.id).first()
    if user:
        user.email = email
        db.commit()
    db.close()
    
    await message.answer("Email принят! Выставляю счет...")
    
    prices = [LabeledPrice(label="Участие в марафоне «МЕТОД»", amount=5000 * 100)]
    token = config.payment_token.get_secret_value()
    
    print(f"DEBUG_INVOICE_START: user={message.from_user.id} token_len={len(token)}", flush=True)

    try:
        await message.answer_invoice(
            title="Марафон «МЕТОД»",
            description="Полный доступ к весеннему марафону трансформации (4 недели)",
            provider_token=token,
            currency="RUB",
            prices=prices,
            payload="marathon_payment",
            start_parameter="marathon_pay",
            need_email=True,
            send_email_to_provider=False
        )
        print(f"DEBUG_INVOICE_OK: user={message.from_user.id}", flush=True)
    except Exception as e:
        print(f"DEBUG_INVOICE_ERROR: user={message.from_user.id} err={e}", flush=True)

    await state.set_state(MarathonState.waiting_for_payment)

@router.callback_query(F.data == "go_to_payment")
async def send_payment_invoice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    print(f"DEBUG: User {callback.from_user.id} clicked pay", flush=True)
    await track_event(callback.from_user.id, "click_pay", callback.from_user.username)
    await callback.answer()
    
    prices = [LabeledPrice(label="Участие в марафоне «МЕТОД»", amount=5000 * 100)]
    token = config.payment_token.get_secret_value()
    
    print(f"DEBUG_INVOICE_START: user={callback.from_user.id} token_len={len(token)}", flush=True)

    try:
        await callback.message.answer_invoice(
            title="Марафон «МЕТОД»",
            description="Полный доступ к весеннему марафону трансформации (4 недели)",
            provider_token=token,
            currency="RUB",
            prices=prices,
            payload="marathon_payment",
            start_parameter="marathon_pay",
            need_email=True,
            send_email_to_provider=False
        )
        print(f"DEBUG_INVOICE_OK: user={callback.from_user.id}", flush=True)
    except Exception as e:
        print(f"DEBUG_INVOICE_ERROR: user={callback.from_user.id} err={e}", flush=True)
    
    await state.set_state(MarathonState.waiting_for_payment)
    await track_event(callback.from_user.id, "payment_started", callback.from_user.username)
    schedule_payment_reminder(bot, callback.from_user.id)

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    print(f"DEBUG_PRECHECKOUT: user={pre_checkout_query.from_user.id} total={pre_checkout_query.total_amount}", flush=True)
    try:
        await pre_checkout_query.answer(ok=True)
        print(f"DEBUG_PRECHECKOUT_OK: user={pre_checkout_query.from_user.id}", flush=True)
    except Exception as e:
        print(f"DEBUG_PRECHECKOUT_ERROR: user={pre_checkout_query.from_user.id} err={e}", flush=True)
        await pre_checkout_query.answer(ok=False, error_message="Ошибка на стороне сервера. Попробуйте позже.")
