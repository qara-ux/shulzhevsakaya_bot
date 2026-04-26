#!/bin/bash

# Start Dashboard in background
echo "Starting Dashboard..."
uvicorn dashboard.api.index:app --host 0.0.0.0 --port ${PORT:-8000} &

# Start Bot in foreground
echo "Starting Bot..."
python3 main.py
