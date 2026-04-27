import os
import httpx
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, Header, HTTPException, Body, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotificationFactory

from .database import engine, get_db, Base, SessionLocal
from .models import AnalyticsEvent, UserRecord, ScheduledBroadcast, BotNode

load_dotenv()
Base.metadata.create_all(bind=engine)

# Migration: Ensure BigInteger for Telegram IDs
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT"))
        conn.execute(text("ALTER TABLE events ALTER COLUMN user_id TYPE BIGINT"))
        conn.commit()
    except Exception as e: pass

app = FastAPI()
scheduler = AsyncIOScheduler(timezone="UTC")
BOT_TOKEN = os.getenv("BOT_TOKEN")

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY

# --- Pydantic Models ---
class BroadcastRequest(BaseModel):
    message: str
    image_url: Optional[str] = None
    filter_type: str
    send_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    is_recurring: bool = False
    recurrence: Optional[Dict[str, Any]] = None

class NodeUpdate(BaseModel):
    title: Optional[str] = None
    content: str
    buttons: List[Dict[str, Any]]
    follow_up_delay: Optional[int] = None
    follow_up_node: Optional[str] = None
    is_start_node: Optional[bool] = False

class AnalyticsRequest(BaseModel):
    user_id: int
    event_name: str
    username: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

# --- API ROUTES ---

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    total_users = db.query(UserRecord).count()
    paid_users = db.query(UserRecord).filter(UserRecord.is_paid == True).count()
    
    # Funnel steps
    starts = db.query(AnalyticsEvent).filter(AnalyticsEvent.event_name == "click_start").count()
    leads = db.query(AnalyticsEvent).filter(AnalyticsEvent.event_name == "contact_node").count()
    payments_started = db.query(AnalyticsEvent).filter(AnalyticsEvent.event_name == "payment_started").count()
    
    return {
        "total_users": total_users,
        "paid_users": paid_users,
        "funnel": {
            "starts": starts,
            "leads": leads,
            "payments": payments_started,
            "success": paid_users
        }
    }

@app.get("/api/users")
async def get_users(db: Session = Depends(get_db)):
    return db.query(UserRecord).order_by(UserRecord.created_at.desc()).all()

@app.post("/api/track")
async def track_event(req: AnalyticsRequest, db: Session = Depends(get_db)):
    user = db.query(UserRecord).filter(UserRecord.telegram_id == req.user_id).first()
    if not user:
        user = UserRecord(telegram_id=req.user_id, username=req.username)
        db.add(user)
    
    if req.event_name == "email_captured" and req.data and "email" in req.data:
        user.email = req.data["email"]
        db.add(AnalyticsEvent(user_id=req.user_id, event_name=req.event_name, data=req.data))
    
    db.add(AnalyticsEvent(user_id=req.user_id, event_name=req.event_name, data=req.data))
    db.commit(); return {"status": "ok"}

@app.post("/api/webhook/yookassa")
async def yookassa_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        notification = WebhookNotificationFactory().create(body)
        payment = notification.object
        if notification.event == "payment.succeeded":
            metadata = payment.metadata
            if metadata and metadata.get("bot_source") == "@method_shulzhevskoy_bot":
                user_id = int(metadata.get("user_id"))
                user = db.query(UserRecord).filter(UserRecord.telegram_id == user_id).first()
                if user:
                    user.is_paid = True
                    db.commit()
                    async with httpx.AsyncClient() as client:
                        await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                            "chat_id": user_id,
                            "text": "🎉 Поздравляем! Оплата прошла успешно.\n\nТеперь вам открыт полный доступ к марафону «МЕТОД».\n\n👉 Ссылка на закрытую группу: https://t.me/+C-xOxlwd-MFmYjZi"
                        })
        return {"status": "ok"}
    except: return {"status": "error"}

# Serve dashboard
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

@app.get("/{path:path}")
async def serve_static(path: str):
    if path.startswith("api"): raise HTTPException(404)
    file_path = os.path.join("dashboard/static", path)
    if os.path.isfile(file_path): return FileResponse(file_path)
    return FileResponse("dashboard/static/index.html")

@app.get("/")
async def idx(): return FileResponse("dashboard/static/index.html")
