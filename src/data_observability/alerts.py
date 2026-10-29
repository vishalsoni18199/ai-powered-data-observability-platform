"""SMTP email alerts. No-op when SMTP_HOST is unset."""

import smtplib
from email.message import EmailMessage

from .config import get_settings


def send_incident_email(incident, recipients: list[str] | None = None) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        return False
    message = EmailMessage()
    message["Subject"] = f"[{incident.severity.upper()}] Data observability: {incident.title}"
    message["From"] = settings.smtp_from
    targets = recipients or [address.strip() for address in settings.smtp_to.split(",") if address.strip()]
    if not targets:
        return False
    message["To"] = ", ".join(targets)
    message.set_content(
        f"Pipeline: {incident.pipeline_id}\nRule: {incident.rule_name}\n"
        f"Details: {incident.details}\nIncident ID: {incident.id}\n"
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_starttls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password or "")
        server.send_message(message)
    return True
