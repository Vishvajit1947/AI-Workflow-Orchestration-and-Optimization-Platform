"""
Email service: send password reset emails.
"""

import logging
from pathlib import Path

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Setup Jinja2 environment for email templates
template_dir = Path(__file__).parent.parent / "email_templates"
jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))


async def send_email(
    to_email: str, subject: str, html_body: str, text_body: str
) -> bool:
    """
    Send an email via SMTP or log it in development mode.
    Returns True on success, False on failure.
    """
    # Development mode: log email to console
    if settings.ENVIRONMENT == "development" or not settings.SMTP_USER:
        logger.info(
            f"\n{'='*60}\n"
            f"[DEV EMAIL]\n"
            f"To: {to_email}\n"
            f"Subject: {subject}\n"
            f"{'='*60}\n"
            f"{text_body}\n"
            f"{'='*60}\n"
        )
        return True

    # Production mode: send via SMTP
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def send_password_reset_email(to_email: str, full_name: str, token: str) -> bool:
    """Send a password reset email with a reset link."""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    template = jinja_env.get_template("password_reset_email.html")
    html_body = template.render(
        full_name=full_name,
        reset_url=reset_url,
        app_name=settings.APP_NAME,
        expire_minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES,
    )

    text_body = f"""
Hello {full_name},

We received a request to reset your password for {settings.APP_NAME}.

Click the link below to reset your password:
{reset_url}

This link will expire in {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes.

If you didn't request this password reset, you can safely ignore this email.

Best regards,
The {settings.APP_NAME} Team
    """.strip()

    return await send_email(
        to_email=to_email,
        subject=f"Reset your {settings.APP_NAME} password",
        html_body=html_body,
        text_body=text_body,
    )
