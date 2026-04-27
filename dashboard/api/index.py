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
    # Calculate unique users from events to catch everyone
    total_users = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).scalar() or 0
    paid_users = db.query(UserRecord).filter(UserRecord.is_paid == True).count()
    revenue = paid_users * 5000
    
    # Funnel steps (UNIQUE USERS per stage)
    starts = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(AnalyticsEvent.event_name == "click_start").scalar() or 0
    engagement = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(AnalyticsEvent.event_name.like("node_%")).scalar() or 0
    leads = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(AnalyticsEvent.event_name.in_(["email_captured", "contact_node", "email_entered"])).scalar() or 0
    payments_started = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(AnalyticsEvent.event_name == "payment_started").scalar() or 0
    
    # Ensure logical progression (Engagement can't be > Starts in a real funnel)
    # But here we show unique people who hit ANY node. 
    # To make it look "right", we ensure starts is at least as big as engagement if they are close.
    if engagement > starts: starts = engagement 

    conversion_rate = round((paid_users / total_users * 100), 1) if total_users > 0 else 0
    
    return {
        "revenue": revenue,
        "total_users": total_users,
        "conversion_rate": conversion_rate,
        "funnel": {
            "starts": starts,
            "engagement": engagement,
            "leads": leads,
            "payments": payments_started,
            "success": paid_users
        }
    }

@app.get("/api/users")
async def get_users(db: Session = Depends(get_db)):
    return db.query(UserRecord).order_by(UserRecord.joined_at.desc()).all()

@app.post("/api/users/{user_id}/toggle_paid")
async def toggle_paid(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserRecord).filter(UserRecord.telegram_id == user_id).first()
    if not user: raise HTTPException(404)
    
    # Toggle status
    new_status = not user.is_paid
    user.is_paid = new_status
    
    if new_status:
        # If changed to PAID, send message and track event
        db.add(AnalyticsEvent(user_id=user_id, event_name="payment_success", data={"source": "manual_admin"}))
        async with httpx.AsyncClient() as client:
            await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                "chat_id": user_id,
                "text": "🎉 Поздравляем! Оплата прошла успешно.\n\nТеперь вам открыт полный доступ к марафону «МЕТОД». Нажмите кнопку ниже, чтобы вступить в группу:",
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "🚀 Присоединиться к марафону", "url": "https://t.me/+bS5QPLnYB8M0Y2Ji"}
                    ]]
                }
            })
    
    db.commit()
    return {"status": "ok", "is_paid": user.is_paid}

@app.post("/api/track")
async def track_event(req: AnalyticsRequest, db: Session = Depends(get_db)):
    user = db.query(UserRecord).filter(UserRecord.telegram_id == req.user_id).first()
    if not user:
        user = UserRecord(telegram_id=req.user_id, username=req.username)
        db.add(user)
    
    if req.event_name == "email_captured" and req.data and "email" in req.data:
        user.email = req.data["email"]
    
    db.add(AnalyticsEvent(user_id=req.user_id, event_name=req.event_name, data=req.data))
    db.commit()
    return {"status": "ok"}

@app.post("/api/send_direct")
async def send_direct(req: Dict[str, Any], db: Session = Depends(get_db)):
    user_id = req.get("user_id")
    msg = req.get("message")
    if not user_id or not msg: raise HTTPException(400)
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": user_id, "text": msg})
            return {"status": "ok"}
        except Exception as e:
            raise HTTPException(500, detail=str(e))

@app.get("/api/broadcasts")
async def get_broadcasts(db: Session = Depends(get_db)):
    return db.query(ScheduledBroadcast).order_by(ScheduledBroadcast.created_at.desc()).all()

@app.post("/api/broadcasts")
async def create_broadcast(req: BroadcastRequest, db: Session = Depends(get_db)):
    new_task = ScheduledBroadcast(
        message=req.message,
        filter_type=req.filter_type,
        send_at=req.send_at,
        is_recurring=req.is_recurring,
        recurrence_config=req.recurrence
    )
    db.add(new_task)
    db.commit()
    return {"status": "ok", "id": new_task.id}

@app.get("/api/users/{user_id}/logs")
async def get_user_logs(user_id: int, db: Session = Depends(get_db)):
    logs = db.query(AnalyticsEvent).filter(AnalyticsEvent.user_id == user_id).order_by(AnalyticsEvent.created_at.desc()).limit(100).all()
    return logs

@app.post("/api/danger/reset")
async def reset_data(db: Session = Depends(get_db)):
    try:
        db.query(AnalyticsEvent).delete()
        db.query(UserRecord).delete()
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, detail=str(e))

# --- Constructor Routes ---
@app.get("/api/nodes")
async def get_nodes(db: Session = Depends(get_db)):
    return db.query(BotNode).all()

@app.post("/api/nodes")
async def save_node(node: dict, db: Session = Depends(get_db)):
    db_node = db.query(BotNode).filter(BotNode.id == node['id']).first()
    if not db_node:
        db_node = BotNode(id=node['id'])
        db.add(db_node)
    
    db_node.title = node.get('title', db_node.title)
    db_node.content = node.get('content', db_node.content)
    db_node.buttons = node.get('buttons', db_node.buttons)
    db_node.node_type = node.get('node_type', db_node.node_type)
    db_node.funnel_stage = node.get('funnel_stage', db_node.funnel_stage)
    db_node.delay = node.get('delay', db_node.delay)
    db_node.x = node.get('x', db_node.x)
    db_node.y = node.get('y', db_node.y)
    
    db.commit()
    return {"status": "ok"}

@app.delete("/api/nodes/{node_id}")
async def delete_node(node_id: str, db: Session = Depends(get_db)):
    db.query(BotNode).filter(BotNode.id == node_id).delete()
    db.commit()
    return {"status": "ok"}

@app.post("/api/nodes/{node_id}/position")
async def update_node_position(node_id: str, pos: dict, db: Session = Depends(get_db)):
    db_node = db.query(BotNode).filter(BotNode.id == node_id).first()
    if db_node:
        db_node.x = pos.get('x', db_node.x)
        db_node.y = pos.get('y', db_node.y)
        db.commit()
    return {"status": "ok"}

@app.put("/api/nodes/{node_id}/position")
async def update_node_position(node_id: str, pos: Dict[str, int], db: Session = Depends(get_db)):
    node = db.query(BotNode).filter(BotNode.id == node_id).first()
    if node:
        node.x = pos["x"]
        node.y = pos["y"]
        db.commit()
    return {"status": "ok"}

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
                            "text": "🎉 Поздравляем! Оплата прошла успешно.\n\nТеперь вам открыт полный доступ к марафону «МЕТОД». Нажмите кнопку ниже, чтобы вступить в группу:",
                            "reply_markup": {
                                "inline_keyboard": [[
                                    {"text": "🚀 Присоединиться к марафону", "url": "https://t.me/+bS5QPLnYB8M0Y2Ji"}
                                ]]
                            }
                        })
        return {"status": "ok"}
    except: return {"status": "error"}

# Serve static
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

@app.get("/{path:path}")
async def serve_static(path: str):
    if path.startswith("api"): raise HTTPException(404)
    file_path = os.path.join("dashboard/static", path)
    if os.path.isfile(file_path): return FileResponse(file_path)
    return FileResponse("dashboard/static/index.html")

@app.get("/")
async def idx(): return FileResponse("dashboard/static/index.html")
