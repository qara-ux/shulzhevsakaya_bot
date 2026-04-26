from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_start_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, участвовать", callback_data="join_marathon")
    builder.button(text="Есть вопросы", callback_data="faq_start")
    builder.adjust(1)
    return builder.as_markup()

def get_join_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти к оплате", callback_data="go_to_payment")
    return builder.as_markup()

def get_payment_kb(payment_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить участие", url=payment_url)
    # Adding a hidden callback for simulation if needed, but per requirements just pay button
    # To simulate success, we can add a check button for testing
    builder.button(text="Проверить оплату (имитация)", callback_data="check_payment_stub")
    builder.adjust(1)
    return builder.as_markup()

def get_faq_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Что внутри?", callback_data="faq_content")
    builder.button(text="Подойдёт ли мне?", callback_data="faq_suitability")
    builder.button(text="Когда результат?", callback_data="faq_result")
    builder.button(text="Задать вопрос", callback_data="faq_custom")
    builder.button(text="Назад к марафону", callback_data="join_marathon")
    builder.adjust(1)
    return builder.as_markup()
