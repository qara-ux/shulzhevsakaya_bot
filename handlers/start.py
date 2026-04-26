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
    # Trigger the 'start' node from the visual constructor
    await send_node(message, "start", state)
