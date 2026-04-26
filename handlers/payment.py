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
    # Get email from the payment info provided by Telegram
    email = message.successful_payment.order_info.email if message.successful_payment.order_info else None
    
    await track_event(message.from_user.id, "payment_success", message.from_user.username, amount=5000, email=email)
    
    from dashboard.api.database import SessionLocal
    from dashboard.api.models import UserRecord
    from services.email_service import send_receipt_email
    
    db = SessionLocal()
    user = db.query(UserRecord).filter(UserRecord.telegram_id == message.from_user.id).first()
    if user:
        user.is_paid = True
        if email: user.email = email # Capture email from payment info
        db.commit()
    db.close()

    if email:
        await send_receipt_email(email, 5000, message.from_user.username or "Участник")

    cancel_reminders(message.from_user.id)
    await state.clear()
    await send_node(message, "success", state)

@router.message(F.text, StateFilter(MarathonState.waiting_for_email))
async def process_email_legacy(message: Message, state: FSMContext, bot: Bot):
    # This handles the case if a DB node still asks for email
    email = message.text.strip()
    from utils.validators import is_valid_email
    if not is_valid_email(email):
        await message.answer("❌ Некорректный email. Попробуйте еще раз или нажмите кнопку оплаты.")
        return

    # Save email and show invoice immediately
    from dashboard.api.database import SessionLocal
    from dashboard.api.models import UserRecord
    db = SessionLocal()
    user = db.query(UserRecord).filter(UserRecord.telegram_id == message.from_user.id).first()
    if user:
        user.email = email
        db.commit()
    db.close()
    
    await message.answer("Email принят! Выставляю счет...")
    
    # Trigger the same invoice logic
    prices = [LabeledPrice(label="Участие в марафоне «МЕТОД»", amount=5000 * 100)]
    await message.answer_invoice(
        title="Марафон «МЕТОД»",
        description="Полный доступ к весеннему марафону трансформации (4 недели)",
        provider_token=config.payment_token.get_secret_value(),
        currency="rub",
        prices=prices,
        payload="marathon_payment",
        start_parameter="marathon_pay",
        need_email=True,
        send_email_to_provider=True
    )
    await state.set_state(MarathonState.waiting_for_payment)

@router.callback_query(F.data == "go_to_payment")
async def send_payment_invoice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await track_event(callback.from_user.id, "click_pay", callback.from_user.username)
    await callback.answer()
    
    # Send Invoice directly without asking for email in chat
    prices = [LabeledPrice(label="Участие в марафоне «МЕТОД»", amount=5000 * 100)]
    
    await callback.message.answer_invoice(
        title="Марафон «МЕТОД»",
        description="Полный доступ к весеннему марафону трансформации (4 недели)",
        provider_token=config.payment_token.get_secret_value(),
        currency="rub",
        prices=prices,
        payload="marathon_payment",
        start_parameter="marathon_pay",
        need_email=True, # Telegram will ask for email in the payment UI
        send_email_to_provider=True
    )
    
    await state.set_state(MarathonState.waiting_for_payment)
    await track_event(callback.from_user.id, "payment_started", callback.from_user.username)
    schedule_payment_reminder(bot, callback.from_user.id)

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    # Telegram requires answering pre_checkout_query within 10 seconds
    await pre_checkout_query.answer(ok=True)
