#!/bin/bash
# Install dependencies
apt update && apt install -y python3-pip python3-venv git screen

# Clone repo
git clone https://github.com/qara-ux/shulzhevsakaya_bot.git
cd shulzhevsakaya_bot

# Setup venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env with REAL tokens
cat <<EOF > .env
BOT_TOKEN=8744218637:AAFmp9PGYdqrXzASvWj3m2eckMItH6rLtA4
ADMIN_IDS=321010140
PAYMENT_TOKEN=381764678:TEST:176335
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=theoctagen@gmail.com
SMTP_PASS=xtna fkhm tlyu qqyf
SMTP_FROM=МЕТОД ШУЛЬЖЕВСКОЙ
EOF

# Make restart script executable and run it
chmod +x restart.sh
./restart.sh

echo "Deployment finished! Dashboard should be at http://45.9.43.62:8000"
