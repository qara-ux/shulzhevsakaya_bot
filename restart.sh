#!/bin/bash

# 1. Kill everything on port 8000 (Dashboard)
echo "Stopping Dashboard..."
lsof -ti :8000 | xargs kill -9 2>/dev/null || true

# 2. Kill all bot processes
echo "Stopping Bot..."
pkill -9 -f "main.py" || true

# 3. Remove PID files
rm -f bot.pid dashboard.pid

# 4. Release sockets
sleep 1

# 5. Detect VENV
VENV_PATH="./venv"
if [ ! -d "$VENV_PATH" ]; then
    VENV_PATH="./.venv"
fi

if [ ! -d "$VENV_PATH" ]; then
    echo "ERROR: Venv not found! Please create it first."
    exit 1
fi

echo "Using venv: $VENV_PATH"

# 6. Start Dashboard
echo "Starting Dashboard..."
nohup $VENV_PATH/bin/python3 -m uvicorn dashboard.api.index:app --host 0.0.0.0 --port 8000 > dashboard.log 2>&1 &
echo $! > dashboard.pid

# 7. Start Bot
echo "Starting Bot..."
nohup $VENV_PATH/bin/python3 main.py > bot.log 2>&1 &
# PID will be written by the bot itself thanks to our new lock logic

echo "Services restarted successfully."
