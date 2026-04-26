import logging
import aiosmtplib
from email.message import EmailMessage
from config import config

logger = logging.getLogger(__name__)

async def send_receipt_email(to_email: str, amount: int, username: str):
    """
    Sends a payment receipt email to the user using SMTP.
    """
    # Skip if SMTP user is not configured
    if not config.smtp_user:
        logger.warning(f"📧 SMTP not configured. Skipping email to {to_email}")
        return False

    subject = "Чек об оплате — Марафон «МЕТОД» 🌸"
    body = f"""
Здравствуйте, {username}!

Подтверждаем вашу оплату участия в весеннем марафоне «МЕТОД».
Сумма: {amount} руб.

Доступ в закрытый канал уже ждет вас в боте! 🚀

С уважением,
Команда марафона «МЕТОД»
"""
    
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.smtp_from or config.smtp_user
    msg["To"] = to_email
    msg.set_content(body)

    try:
        await aiosmtplib.send(
            msg,
            hostname=config.smtp_host,
            port=config.smtp_port,
            username=config.smtp_user,
            password=config.smtp_pass.get_secret_value(),
            use_tls=(config.smtp_port == 465),
            start_tls=(config.smtp_port == 587)
        )
        logger.info(f"📧 Email receipt sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email receipt to {to_email}: {e}")
        return False
