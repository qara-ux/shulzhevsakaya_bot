from aiogram import Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.state import any_state
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from handlers.dynamic import send_node

router = Router()

@router.message(CommandStart(), StateFilter(any_state))
async def cmd_start(message: Message, state: FSMContext):
    # Always clear any stuck state
    await state.clear()
    
    # Try to find the node marked as 'start' in the database first,
    # if not found, send_node will fall back to is_start_node=True
    await send_node(message, "entry", state)
