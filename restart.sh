#!/bin/bash

# 1. Kill everything on port 8000 (Dashboard)
echo "Stopping Dashboard..."
lsof -ti :8000 | xargs kill -9 2>/dev/null || true

# 2. Kill all bot processes by name strictly
echo "Stopping Bot..."
pkill -9 -f "main.py" || true
pgrep -f "main.py" | xargs kill -9 2>/dev/null || true

# 3. Double check and remove PID files
rm -f bot.pid dashboard.pid

# 4. Wait a bit for system to release sockets
sleep 2

# 5. Start Dashboard
echo "Starting Dashboard..."
nohup ./.venv/bin/python3 -m uvicorn dashboard.api.index:app --host 0.0.0.0 --port 8000 > dashboard.log 2>&1 &
echo $! > dashboard.pid

# 6. Start Bot
echo "Starting Bot..."
nohup ./.venv/bin/python3 main.py > bot.log 2>&1 &
# PID will be written by the bot itself thanks to our new lock logic

echo "Services restarted successfully."
