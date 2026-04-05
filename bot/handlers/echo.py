from aiogram import Router, F
from aiogram.types import Message

router = Router()


@router.message(F.text)
async def echo_handler(message: Message) -> None:
    await message.answer(f"Вы написали: <i>{message.text}</i>", parse_mode="HTML")
