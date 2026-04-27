from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
import os

MANAGER_ID = 5774702671

class NotificationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Check if it's a message with text and not a command
        if isinstance(event, Message) and event.text and not event.text.startswith('/'):
            user = event.from_user
            username = f"@{user.username}" if user.username else user.full_name
            
            notification_text = (
                f"📬 **Сообщение менеджеру!**\n\n"
                f"👤 **От:** {username}\n"
                f"🆔 **ID:** `{user.id}`\n"
                f"💬 **Текст:** {event.text}"
            )
            
            # Send to manager (using the bot from data)
            bot = data.get("bot")
            if bot and user.id != MANAGER_ID:
                try:
                    await bot.send_message(MANAGER_ID, notification_text, parse_mode="Markdown")
                except Exception as e:
                    print(f"❌ Error sending notification to manager: {e}")

        return await handler(event, data)
