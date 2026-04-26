#!/bin/bash

# Ensure the bot talks to the dashboard on the correct port
export ANALYTICS_API_URL="http://127.0.0.1:${PORT:-8000}"
echo "Analytics URL set to: $ANALYTICS_API_URL"

# Start Dashboard in background
echo "Starting Dashboard on port ${PORT:-8000}..."
uvicorn dashboard.api.index:app --host 0.0.0.0 --port ${PORT:-8000} &

# Start Bot in foreground
echo "Starting Bot..."
python3 main.py
