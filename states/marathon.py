from aiogram.fsm.state import State, StatesGroup

class MarathonState(StatesGroup):
    waiting_for_join_decision = State()
    waiting_for_email = State()
    waiting_for_payment = State()
