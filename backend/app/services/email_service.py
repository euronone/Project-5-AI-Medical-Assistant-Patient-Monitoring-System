"""Transactional email — Resend, SendGrid, or SMTP.

Env (checked in order):
  RESEND_API_KEY — https://resend.com
  RESEND_FROM_EMAIL — verified sender
  SENDGRID_API_KEY — SendGrid v3
  SENDGRID_FROM_EMAIL — verified sender
  SMTP_* — SMTP fallback
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

logger = structlog.get_logger(__name__)


def get_email_provider_status() -> dict[str, str | bool]:
    """Return current outbound email provider configuration status."""
    smtp_host = (os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER") or "").strip()
    smtp_user = (
        os.getenv("SMTP_USER")
        or os.getenv("SMTP_USERNAME")
        or os.getenv("MAIL_USERNAME")
        or os.getenv("MAIL_DEFAULT_SENDER")
        or os.getenv("SMTP_FROM_EMAIL")
        or ""
    ).strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or "").strip()
    resend_key = (os.getenv("RESEND_API_KEY") or "").strip()
    sg_key = (os.getenv("SENDGRID_API_KEY") or "").strip()

    if smtp_host and smtp_user and smtp_password:
        return {"configured": True, "primary": "smtp"}
    if resend_key:
        return {"configured": True, "primary": "resend"}
    if sg_key:
        return {"configured": True, "primary": "sendgrid"}
    return {"configured": False, "primary": "none"}


def send_appointment_confirmation_emails(
    patient_email: str | None,
    patient_display_name: str,
    doctor_email: str | None,
    doctor_display_name: str,
    scheduled_at: datetime,
    appointment_type: str,
    appointment_id: str,
    duration_minutes: int,
) -> tuple[bool, bool]:
    """Send confirmation to patient and provider. Returns (patient_sent, doctor_sent)."""
    when = scheduled_at.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    type_label = appointment_type.replace("_", " ").title()

    patient_subject = "Your MedAssist AI appointment is confirmed"
    patient_text = (
        f"Hello {patient_display_name},\n\n"
        f"Your appointment is confirmed.\n\n"
        f"Provider: {doctor_display_name}\n"
        f"When: {when}\n"
        f"Type: {type_label}\n"
        f"Duration: {duration_minutes} minutes\n"
        f"Reference: {appointment_id}\n\n"
        f"If you need to reschedule, use the Appointments section in your portal.\n\n"
        f"— MedAssist AI\n"
    )
    patient_html = f"""<!DOCTYPE html><html><body style="font-family:system-ui,sans-serif;line-height:1.5">
<p>Hello {patient_display_name},</p>
<p><strong>Your appointment is confirmed.</strong></p>
<ul>
<li><strong>Provider:</strong> {doctor_display_name}</li>
<li><strong>When:</strong> {when}</li>
<li><strong>Type:</strong> {type_label}</li>
<li><strong>Duration:</strong> {duration_minutes} minutes</li>
<li><strong>Reference:</strong> {appointment_id}</li>
</ul>
<p>If you need to reschedule, open the <strong>Appointments</strong> tab in your patient portal.</p>
<p>— MedAssist AI</p>
</body></html>"""

    doctor_subject = f"New appointment — {patient_display_name}"
    doctor_text = (
        f"Hello {doctor_display_name},\n\n"
        f"A patient has booked an appointment with you.\n\n"
        f"Patient: {patient_display_name}\n"
        f"When: {when}\n"
        f"Type: {type_label}\n"
        f"Duration: {duration_minutes} minutes\n"
        f"Reference: {appointment_id}\n\n"
        f"View details in your MedAssist AI provider schedule.\n\n"
        f"— MedAssist AI\n"
    )
    doctor_html = f"""<!DOCTYPE html><html><body style="font-family:system-ui,sans-serif;line-height:1.5">
<p>Hello {doctor_display_name},</p>
<p><strong>A new appointment was booked with you.</strong></p>
<ul>
<li><strong>Patient:</strong> {patient_display_name}</li>
<li><strong>When:</strong> {when}</li>
<li><strong>Type:</strong> {type_label}</li>
<li><strong>Duration:</strong> {duration_minutes} minutes</li>
<li><strong>Reference:</strong> {appointment_id}</li>
</ul>
<p>— MedAssist AI</p>
</body></html>"""

    patient_ok = (
        _try_send_email((patient_email or "").strip(), patient_subject, patient_text, patient_html)
        if (patient_email or "").strip()
        else False
    )
    doctor_ok = (
        _try_send_email((doctor_email or "").strip(), doctor_subject, doctor_text, doctor_html)
        if (doctor_email or "").strip()
        else False
    )

    if not patient_ok and not (patient_email or "").strip():
        logger.warning("appointment_email_skipped_no_patient_email", appointment_id=appointment_id)
    if not doctor_ok and not (doctor_email or "").strip():
        logger.warning("appointment_email_skipped_no_doctor_email", appointment_id=appointment_id)
    if not patient_ok and (patient_email or "").strip():
        logger.warning("appointment_patient_email_failed", appointment_id=appointment_id)
    if not doctor_ok and (doctor_email or "").strip():
        logger.warning("appointment_doctor_email_failed", appointment_id=appointment_id)

    return patient_ok, doctor_ok


def _try_send_email(to_email: str, subject: str, text: str, html: str) -> bool:
    # 1) SMTP first (requested): supports Gmail/app-password setups.
    smtp_host = (os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER") or "").strip()
    if smtp_host and (os.getenv("SMTP_USER") or "").strip() and (os.getenv("SMTP_PASSWORD") or "").strip():
        if _send_smtp(to_email, subject, text, html):
            return True
    # Common aliases used in some Flask/Google SMTP setups
    smtp_user_alias = (
        os.getenv("SMTP_USERNAME")
        or os.getenv("MAIL_USERNAME")
        or os.getenv("MAIL_DEFAULT_SENDER")
        or os.getenv("SMTP_FROM_EMAIL")
        or ""
    ).strip()
    if smtp_host and smtp_user_alias and (os.getenv("SMTP_PASSWORD") or "").strip():
        if _send_smtp(to_email, subject, text, html):
            return True

    # 2) Resend fallback
    resend_key = (os.getenv("RESEND_API_KEY") or "").strip()
    if resend_key:
        if _send_resend(resend_key, to_email, subject, text, html):
            return True

    # 3) SendGrid fallback
    sg_key = (os.getenv("SENDGRID_API_KEY") or "").strip()
    if sg_key:
        if _send_sendgrid(sg_key, to_email, subject, text, html):
            return True

    logger.warning("email_skipped_no_provider_configured", to_email=to_email)
    return False


def _resend_from_header() -> str:
    raw = (os.getenv("RESEND_FROM_EMAIL") or os.getenv("RESEND_FROM") or "").strip()
    if raw:
        if "<" in raw and ">" in raw:
            return raw
        return f"MedAssist AI <{raw}>"
    return "MedAssist AI <onboarding@resend.dev>"


def _send_resend(api_key: str, to_email: str, subject: str, text: str, html: str) -> bool:
    payload = {
        "from": _resend_from_header(),
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": text,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MedAssistAI-Backend/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            if code in (200, 201, 202):
                logger.info("resend_mail_sent", to_email=to_email)
                return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:800]
        logger.error("resend_http_error", status=e.code, body=body)
    except Exception as e:
        logger.error("resend_send_failed", error=str(e))
    return False


def _send_sendgrid(api_key: str, to_email: str, subject: str, text: str, html: str) -> bool:
    from_email = (
        (os.getenv("SENDGRID_FROM_EMAIL") or os.getenv("SENDGRID_FROM") or "noreply@medassist.local")
        .strip()
    )
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email, "name": "MedAssist AI"},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text},
            {"type": "text/html", "value": html},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            if code in (200, 202):
                logger.info("sendgrid_mail_sent", to_email=to_email)
                return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        logger.error("sendgrid_http_error", status=e.code, body=body)
    except Exception as e:
        logger.error("sendgrid_send_failed", error=str(e))
    return False


def _send_smtp(to_email: str, subject: str, text: str, html: str) -> bool:
    host = (os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER") or "").strip()
    if not host:
        raise KeyError("SMTP_HOST/SMTP_SERVER not set")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = (
        os.getenv("SMTP_USER")
        or os.getenv("SMTP_USERNAME")
        or os.getenv("MAIL_USERNAME")
        or os.getenv("MAIL_DEFAULT_SENDER")
        or os.getenv("SMTP_FROM_EMAIL")
        or ""
    ).strip()
    if not user:
        raise KeyError("SMTP_USER/MAIL_DEFAULT_SENDER not set")
    password = (os.getenv("SMTP_PASSWORD") or "").strip()
    if not password:
        raise KeyError("SMTP_PASSWORD not set")
    # Gmail app passwords are often copied with spaces; strip those safely for gmail hosts.
    if "gmail.com" in host and " " in password:
        password = password.replace(" ", "")
    from_email = (os.getenv("SMTP_FROM_EMAIL") or os.getenv("MAIL_DEFAULT_SENDER") or user).strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.sendmail(from_email, [to_email], msg.as_string())
        logger.info("smtp_mail_sent", to_email=to_email)
        return True
    except Exception as e:
        logger.error("smtp_send_failed", error=str(e))
        return False
