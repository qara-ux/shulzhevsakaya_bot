from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from states.marathon import MarathonState
from dashboard.api.database import SessionLocal
from dashboard.api.models import BotNode, UserRecord
from services.analytics import track_event
from services.scheduler import scheduler
from datetime import datetime, timedelta

router = Router()

def get_node_keyboard(buttons):
    builder = InlineKeyboardBuilder()
    for btn in buttons:
        if btn.get('url'):
            builder.row(types.InlineKeyboardButton(text=btn['text'], url=btn['url']))
        else:
            builder.row(types.InlineKeyboardButton(text=btn['text'], callback_data=f"node:{btn['next_node']}"))
    return builder.as_markup()

async def exec_follow_up(bot: Bot, chat_id: int, node_id: str):
    # Helper for scheduler to trigger a node
    print(f"Triggering follow-up node {node_id} for {chat_id}")
    await send_node_core(bot, chat_id, node_id)

async def send_node_core(bot: Bot, chat_id: int, node_id: str, state=None):
    db = SessionLocal()
    try:
        if node_id == "contact" and state:
            await state.set_state(MarathonState.waiting_for_email)
            print(f"DEBUG: Core state set for {chat_id}")

        node = db.query(BotNode).filter(BotNode.id == node_id).first()
        if not node: return

        text = node.content
        kb = get_node_keyboard(node.buttons)

        if node.image_url:
            await bot.send_photo(chat_id, photo=node.image_url, caption=text, reply_markup=kb)
        else:
            await bot.send_message(chat_id, text=text, reply_markup=kb)

        # Update user record
        user = db.query(UserRecord).filter(UserRecord.telegram_id == chat_id).first()
        if user:
            user.current_node = node_id
            db.commit()
    finally:
        db.close()

async def send_node(message_or_call, node_id: str, state: FSMContext = None):
    db = SessionLocal()
    try:
        user_id = message_or_call.from_user.id
        
        # CRITICAL: If this is the contact node, set the email waiting state
        if node_id == "contact" and state:
            print(f"DEBUG: Setting state waiting_for_email via send_node for {user_id}")
            await state.set_state(MarathonState.waiting_for_email)

        node = db.query(BotNode).filter(BotNode.id == node_id).first()
        if not node:
            node = db.query(BotNode).filter(BotNode.is_start_node == True).first()
            if not node: return
            node_id = node.id

        text = node.content
        kb = get_node_keyboard(node.buttons)

        # Cancel any pending follow-ups for this user
        job_id = f"fu_{user_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        # UI Response
        if isinstance(message_or_call, types.Message):
            if node.image_url: await message_or_call.bot.send_photo(user_id, photo=node.image_url, caption=text, reply_markup=kb)
            else: await message_or_call.bot.send_message(user_id, text=text, reply_markup=kb)
        else:
            # Always send a NEW message instead of editing the previous one
            if node.image_url: 
                await message_or_call.bot.send_photo(user_id, photo=node.image_url, caption=text, reply_markup=kb)
            else: 
                await message_or_call.bot.send_message(user_id, text=text, reply_markup=kb)

        # Update DB
        user = db.query(UserRecord).filter(UserRecord.telegram_id == user_id).first()
        if not user:
            user = UserRecord(telegram_id=user_id, username=message_or_call.from_user.username)
            db.add(user)
        user.current_node = node_id
        db.commit()

        # Schedule Follow-up if exists
        if node.follow_up_delay and node.follow_up_node:
            print(f"Scheduling follow-up {node.follow_up_node} in {node.follow_up_delay}m for {user_id}")
            scheduler.add_job(
                exec_follow_up, "date",
                run_date=datetime.now() + timedelta(minutes=node.follow_up_delay),
                args=[message_or_call.bot, user_id, node.follow_up_node],
                id=job_id
            )

        await track_event(user_id, f"node_{node_id}")
    finally:
        db.close()

from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import any_state

@router.callback_query(F.data.startswith("node:"), StateFilter(any_state))
async def handle_node_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    node_id = callback.data.split(":")[1]
    print(f"DEBUG: Processing node callback: {node_id}")
    
    if node_id == "pay":
        from .payment import send_payment_invoice
        await send_payment_invoice(callback, state, callback.bot)
        return

    # Track as confirmation click
    await track_event(callback.from_user.id, "click_start")
    
    await send_node(callback, node_id, state)
    await callback.answer()

@router.message(F.text)
async def handle_all_messages(message: types.Message, state: FSMContext):
    if message.text.startswith("/"): return # Ignore commands here
    
    # Track the message even if we ignore it in logic
    await track_event(
        message.from_user.id, 
        "message_received", 
        message.from_user.username,
        text=message.text
    )

    current_state = await state.get_state()
    print(f"DEBUG: Catch-all message from {message.from_user.id}, state: {current_state}")
    
    if current_state is not None:
        return

    # If no state, ignore silently.
    return

    # If no state and not in contact node, ignore silently to prevent confusing behavior.
