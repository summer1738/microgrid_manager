"""
Send OTP by email for registration verification.
Uses SMTP when configured via env; otherwise logs OTP to console (dev).
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# Env: SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD, MAIL_FROM (default SMTP_USER)
def send_otp_email(to_email: str, otp: str) -> bool:
    """
    Send OTP code to the given email.
    Returns True if sent (or logged in dev), False on error.
    Always logs OTP to console for faster testing.
    """
    # Always log OTP to console for dev/testing
    print(f"[OTP] {to_email} → {otp}")

    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("MAIL_FROM", user or "noreply@microgrid.local").strip()

    if not host or not user or not password:
        logger.warning(
            "SMTP not configured (SMTP_HOST, SMTP_USER, SMTP_PASSWORD). "
            "OTP for %s: %s (check server logs in dev)",
            to_email,
            otp,
        )
        return True

    subject = "Your verification code — Microgrid Manager"
    body = f"""Hello,

Your verification code for Microgrid Manager registration is:

  {otp}

This code expires in 10 minutes. If you did not request this, please ignore this email.
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        return True
    except Exception as e:
        logger.exception("Failed to send OTP email to %s: %s", to_email, e)
        return False
