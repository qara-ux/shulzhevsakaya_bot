import httpx
import logging
import asyncio
from config import config

logger = logging.getLogger("marathon_analytics")
logger.setLevel(logging.INFO)

async def track_event(user_id: int, event_name: str, username: str = None, **kwargs):
    """
    Sends an analytics event to the Dashboard API.
    """
    # 1. Log locally
    extra = f" | {kwargs}" if kwargs else ""
    logger.info(f"USER:{user_id} | EVENT:{event_name}{extra}")
    print(f"DEBUG_ANALYTICS: user_id={user_id}, username={username}, event={event_name}, data={kwargs}")

    # 2. Send to Dashboard API
    payload = {
        "user_id": user_id,
        "event_name": event_name,
        "username": username,
        "data": kwargs
    }
    
    headers = {
        "X-API-Key": config.analytics_api_key
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{config.analytics_api_url}/api/track",
                json=payload,
                headers=headers,
                timeout=5.0
            )
            if resp.status_code != 200:
                logger.error(f"Analytics API returned {resp.status_code}: {resp.text}")
                # Optional: notify admin about the failure
                if "node_entry" in event_name: # Only notify on first event to avoid spam
                    from aiogram import Bot
                    bot = Bot(token=config.bot_token.get_secret_value())
                    await bot.send_message(
                        config.admin_id, 
                        f"⚠️ <b>ОШИБКА АНАЛИТИКИ</b>\nURL: {config.analytics_api_url}\nStatus: {resp.status_code}\nResponse: {resp.text[:200]}"
                    )
                    await bot.session.close()
    except Exception as e:
        logger.error(f"Failed to send analytics to dashboard: {e}")
