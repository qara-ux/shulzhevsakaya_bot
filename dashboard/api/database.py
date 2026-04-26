import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./analytics.db")

# Log the absolute path for debugging
import os
db_path = DATABASE_URL.replace("sqlite:///", "")
if not DATABASE_URL.startswith("postgres"):
    print(f"DEBUG_DB: Absolute path is {os.path.abspath(db_path)}")

# For PostgreSQL (Supabase), replace 'postgres://' with 'postgresql://' for SQLAlchemy 1.4+
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Enable WAL mode for SQLite to handle concurrent access better
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

# Enable WAL mode for SQLite
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
