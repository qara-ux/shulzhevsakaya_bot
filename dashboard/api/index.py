import os
import httpx
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, Header, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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
        print("MIGRATION: Successfully upgraded to BigInteger")
    except Exception as e:
        print(f"MIGRATION: Skip or fail (likely sqlite or already done): {e}")

app = FastAPI()
scheduler = AsyncIOScheduler(timezone="UTC")
BOT_TOKEN = os.getenv("BOT_TOKEN")

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

class NodeCreate(BaseModel):
    id: str
    title: str
    content: str
    buttons: List[Dict[str, Any]]
    x: Optional[int] = 100
    y: Optional[int] = 100
    follow_up_delay: Optional[int] = None
    follow_up_node: Optional[str] = None
    is_start_node: Optional[bool] = False

class PositionUpdate(BaseModel):
    x: int
    y: int

# --- CORE LOGIC ---

async def execute_broadcast(broadcast_id: int):
    db = SessionLocal()
    try:
        job = db.query(ScheduledBroadcast).filter(ScheduledBroadcast.id == broadcast_id).first()
        if not job or not job.is_active: return
        
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        if job.end_at and now > job.end_at.replace(tzinfo=timezone.utc):
            job.is_active = False
            db.commit(); return
        query = db.query(UserRecord.telegram_id)
        if job.filter_type == "paid": query = query.filter(UserRecord.is_paid == True)
        elif job.filter_type == "unpaid": query = query.filter(UserRecord.is_paid == False)
        target_ids = [r[0] for r in query.all()]
        async with httpx.AsyncClient() as client:
            for tid in target_ids:
                try:
                    p = {"chat_id": tid}
                    if job.image_url:
                        p.update({"photo": job.image_url, "caption": job.message})
                        await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", json=p)
                    else:
                        p.update({"text": job.message})
                        await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=p)
                    await asyncio.sleep(0.05)
                except: pass
        if not job.is_recurring:
            job.is_sent = True
            job.is_active = False
        db.commit()
    finally: db.close()

def schedule_job_in_memory(job):
    if job.is_recurring:
        days = ",".join(map(str, job.recurrence_config['days']))
        h, m = job.recurrence_config['time'].split(':')
        scheduler.add_job(execute_broadcast, CronTrigger(day_of_week=days, hour=h, minute=m, end_date=job.end_at), 
                          args=[job.id], id=f"job_{job.id}", replace_existing=True)
    elif job.send_at:
        from datetime import timezone
        # Ensure we don't skip a job that was scheduled for 'now'
        scheduler.add_job(execute_broadcast, 'date', run_date=job.send_at, 
                          args=[job.id], id=f"job_{job.id}", replace_existing=True)

@app.on_event("startup")
async def startup():
    scheduler.start()
    db = SessionLocal()
    try:
        active_jobs = db.query(ScheduledBroadcast).filter(ScheduledBroadcast.is_active == True).all()
        for job in active_jobs:
            try: schedule_job_in_memory(job)
            except: pass
    finally: db.close()

# --- API ENDPOINTS ---

@app.get("/api/nodes")
async def get_nodes(db: Session = Depends(get_db)): return db.query(BotNode).all()

@app.get("/api/nodes/{node_id}")
async def get_node(node_id: str, db: Session = Depends(get_db)):
    node = db.query(BotNode).filter(BotNode.id == node_id).first()
    if not node: raise HTTPException(404)
    return node

@app.put("/api/nodes/{node_id}")
async def update_node(node_id: str, req: NodeUpdate, db: Session = Depends(get_db)):
    node = db.query(BotNode).filter(BotNode.id == node_id).first()
    if not node: raise HTTPException(404)
    node.title, node.content, node.buttons = req.title, req.content, req.buttons
    node.follow_up_delay = req.follow_up_delay
    node.follow_up_node = req.follow_up_node
    node.is_start_node = req.is_start_node
    db.commit(); return {"status": "ok"}

@app.put("/api/nodes/{node_id}/position")
async def update_pos(node_id: str, req: PositionUpdate, db: Session = Depends(get_db)):
    node = db.query(BotNode).filter(BotNode.id == node_id).first()
    if not node: raise HTTPException(404)
    node.x, node.y = req.x, req.y
    db.commit(); return {"status": "ok"}

@app.post("/api/nodes")
async def create_node(req: NodeCreate, db: Session = Depends(get_db)):
    node = BotNode(id=req.id, title=req.title, content=req.content, buttons=req.buttons, x=req.x, y=req.y, follow_up_delay=req.follow_up_delay, follow_up_node=req.follow_up_node, is_start_node=req.is_start_node)
    db.add(node); db.commit(); return {"status": "ok"}
@app.post("/api/users/{user_id}/pay")
async def mark_user_paid(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserRecord).filter(UserRecord.telegram_id == user_id).first()
    if user:
        user.is_paid = True
        db.commit()
    return {"status": "ok"}

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    tot = db.query(func.count(UserRecord.telegram_id)).scalar() or 0
    paid = db.query(func.count(UserRecord.telegram_id)).filter(UserRecord.is_paid == True).scalar() or 0
    
    # Calculate revenue from unique payment_success events
    total_payments = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(AnalyticsEvent.event_name == "payment_success").scalar() or 0
    revenue = total_payments * 5000
    
    # Funnel steps
    starts = tot
    leads = db.query(func.count(UserRecord.telegram_id)).filter(UserRecord.email != None).scalar() or 0
    checkout = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(AnalyticsEvent.event_name == "payment_started").scalar() or 0
    payments = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(AnalyticsEvent.event_name == "payment_success").scalar() or 0
    success = paid

    return {
        "total_users": tot, 
        "paid_users": paid, 
        "revenue": revenue, 
        "conversion_rate": round(paid/tot*100, 2) if tot else 0,
        "funnel": {
            "starts": starts,
            "leads": leads,
            "checkout": checkout,
            "payments": payments,
            "success": success
        }
    }

@app.get("/api/users")
async def get_users(db: Session = Depends(get_db)): 
    return db.query(UserRecord).order_by(UserRecord.joined_at.desc()).all()

@app.get("/api/planner/list")
async def list_planner(db: Session = Depends(get_db)):
    return db.query(ScheduledBroadcast).order_by(ScheduledBroadcast.created_at.desc()).all()

@app.post("/api/planner")
async def create_plan(req: BroadcastRequest, db: Session = Depends(get_db)):
    job = ScheduledBroadcast(message=req.message, image_url=req.image_url, filter_type=req.filter_type, send_at=req.send_at, end_at=req.end_at, is_recurring=req.is_recurring, recurrence_config=req.recurrence, is_active=True)
    db.add(job); db.commit(); db.refresh(job); schedule_job_in_memory(job); return {"status": "ok"}

@app.delete("/api/planner/{job_id}")
async def del_plan(job_id: int, db: Session = Depends(get_db)):
    db.query(ScheduledBroadcast).filter(ScheduledBroadcast.id == job_id).delete(); db.commit()
    try: scheduler.remove_job(f"job_{job_id}")
    except: pass
    return {"status": "ok"}

class TrackRequest(BaseModel):
    user_id: int
    event_name: str
    username: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

@app.post("/api/track")
async def track(req: TrackRequest, db: Session = Depends(get_db), x_api_key: str = Header(None)):
    if x_api_key != os.getenv("ANALYTICS_API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    print(f"📡 ANALYTICS_RECEIVE: {req.event_name} from user {req.user_id} (@{req.username})")
    user = db.query(UserRecord).filter(UserRecord.telegram_id == req.user_id).first()
    if not user:
        user = UserRecord(telegram_id=req.user_id, username=req.username)
        db.add(user)
        db.flush()
    
    if req.username: user.username = req.username
    
    # NEW: Automatically capture email from event data if present
    if req.data and "email" in req.data:
        user.email = req.data["email"]
        print(f"📧 Captured Email: {user.email} for user {user.telegram_id}")

    db.add(AnalyticsEvent(user_id=req.user_id, event_name=req.event_name, data=req.data))
    db.commit(); return {"status": "ok"}

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

@app.get("/api/logs/{user_id}")
async def get_user_logs(user_id: str, db: Session = Depends(get_db)):
    return db.query(AnalyticsEvent).filter(AnalyticsEvent.user_id == int(user_id)).order_by(AnalyticsEvent.created_at.desc()).all()

app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
@app.get("/")
async def idx(): return FileResponse("dashboard/static/index.html")
