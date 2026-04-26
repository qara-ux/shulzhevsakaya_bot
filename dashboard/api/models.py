from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, ForeignKey, BigInteger
from datetime import datetime
from .database import Base

# --- Existing Models ---
class AnalyticsEvent(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    event_name = Column(String, index=True)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserRecord(Base):
    __tablename__ = "users"
    telegram_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    email = Column(String, nullable=True)
    is_paid = Column(Boolean, default=False)
    current_node = Column(String, default="start") # Track where user is in the flow
    joined_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ScheduledBroadcast(Base):
    __tablename__ = "scheduled_broadcasts"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(String)
    image_url = Column(String, nullable=True)
    filter_type = Column(String)
    send_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurrence_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# --- New: Bot Constructor Models ---
class BotNode(Base):
    __tablename__ = "bot_nodes"
    id = Column(String, primary_key=True, index=True) # e.g. "start", "after_payment", "main_menu"
    title = Column(String, nullable=True) # For admin visibility
    content = Column(String) # Message text
    image_url = Column(String, nullable=True)
    # Buttons format: [{"text": "Buy", "next_node": "payment_screen", "url": null}, ...]
    buttons = Column(JSON, default=[]) 
    is_start_node = Column(Boolean, default=False)
    x = Column(Integer, default=0)
    y = Column(Integer, default=0)
    # Follow-up (dozhim) logic
    follow_up_delay = Column(Integer, nullable=True) # in minutes
    follow_up_node = Column(String, nullable=True) # ID of next node if no action
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
