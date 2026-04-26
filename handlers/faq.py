from aiogram import Router, F
from aiogram.types import CallbackQuery
from keyboards.builders import get_faq_kb
from services.analytics import track_event

router = Router()

@router.callback_query(F.data == "faq_start")
async def process_faq_start(callback: CallbackQuery):
    await callback.answer()
    await track_event(callback.from_user.id, "faq_viewed")
    await callback.message.answer("Отвечу коротко 👇", reply_markup=get_faq_kb())

@router.callback_query(F.data == "faq_content")
async def faq_content(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Что внутри:\nТренировки каждый день + питание + поддержка")

@router.callback_query(F.data == "faq_suitability")
async def faq_suitability(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Подойдёт ли:\nДа, подходит даже если ты начинаешь с нуля")

@router.callback_query(F.data == "faq_result")
async def faq_result(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Когда результат:\nПервые изменения уже через 1–2 недели")

@router.callback_query(F.data == "faq_custom")
async def faq_custom(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Напиши свой вопрос, и я отвечу тебе в ближайшее время! (или просто напиши @admin_username)")
