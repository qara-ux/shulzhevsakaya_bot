from dashboard.api.database import engine, SessionLocal
from dashboard.api.models import Base, BotNode
from sqlalchemy import text

def migrate():
    print("Starting migration...")
    with engine.connect() as conn:
        # Check if columns exist and add them if missing
        columns_to_add = [
            ("node_type", "VARCHAR DEFAULT 'main'"),
            ("funnel_stage", "VARCHAR DEFAULT 'none'"),
            ("delay", "VARCHAR"),
            ("parent_node_id", "VARCHAR"),
            ("x", "FLOAT DEFAULT 100.0"),
            ("y", "FLOAT DEFAULT 100.0")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                conn.execute(text(f"ALTER TABLE bot_nodes ADD COLUMN {col_name} {col_type}"))
                print(f"Added column: {col_name}")
            except Exception as e:
                print(f"Column {col_name} might already exist or error: {e}")
        
        conn.commit()
    print("Migration finished!")

if __name__ == "__main__":
    migrate()
