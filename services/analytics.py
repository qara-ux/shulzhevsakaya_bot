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

    # 2. Direct Database Write (Reliable for Railway/Single Container)
    from dashboard.api.database import SessionLocal
    from dashboard.api.models import AnalyticsEvent, UserRecord
    
    db = SessionLocal()
    try:
        # Ensure user exists
        user = db.query(UserRecord).filter(UserRecord.telegram_id == user_id).first()
        if not user:
            user = UserRecord(telegram_id=user_id, username=username)
            db.add(user)
            db.flush()
        
        if username:
            user.username = username
        
        # Save event
        event = AnalyticsEvent(user_id=user_id, event_name=event_name, data=kwargs)
        db.add(event)
        db.commit()
    except Exception as e:
        logger.error(f"Direct analytics write failed: {e}")
        db.rollback()
    finally:
        db.close()
