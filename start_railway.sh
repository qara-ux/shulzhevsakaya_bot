#!/bin/bash

# Ensure database tables exist
python3 -c "from dashboard.api.database import engine, Base; from dashboard.api.models import *; Base.metadata.create_all(bind=engine)"

# Start Dashboard in background
echo "Starting Dashboard..."
uvicorn dashboard.api.index:app --host 0.0.0.0 --port ${PORT:-8000} &

# Start Bot in foreground
echo "Starting Bot..."
python3 main.py
