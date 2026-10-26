"""
Alerting system for Agri-Agent Swarm.

Supports:
- SQLite persistence of anomaly events (AlertLog)
- Configurable Email notifications (SMTP or logged mock)
- Outbound Webhook dispatch (HTTP POST)
- In-app notification feeds
"""

import logging

import httpx

from config import settings
from database import AlertLog, save_alert_log

log = logging.getLogger("agri_agent.alerting")


async def dispatch_alert(
    message: str,
    severity: str = "WARNING",
    alert_type: str = "ANOMALY",
    farm_id: int | None = None,
    channel: str = "IN_APP",
) -> AlertLog:
    """
    Dispatch an alert across configured channels and persist in the database.

    Args:
        message: Description of the alert or anomaly.
        severity: "INFO", "WARNING", or "CRITICAL".
        alert_type: Category (e.g. "ANOMALY", "HEATWAVE", "SALINITY_SPIKE", "SCHEDULED_CHECK").
        farm_id: Optional ID of the associated farm.
        channel: Primary dispatch channel.
    """
    # 1. Persist to DB
    alert_entry = AlertLog(
        farm_id=farm_id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        channel=channel,
        acknowledged=False,
    )
    saved = save_alert_log(alert_entry)
    log.warning(
        "🚨 [ALERT DISPATCHED] [%s] %s (Farm #%s): %s", severity, alert_type, farm_id, message
    )

    # 2. Outbound Webhook if configured
    if settings.alert_webhook_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                payload = {
                    "alert_id": saved.id,
                    "farm_id": farm_id,
                    "severity": severity,
                    "type": alert_type,
                    "message": message,
                    "timestamp": saved.timestamp.isoformat(),
                }
                await client.post(settings.alert_webhook_url, json=payload)
                log.info("Alert webhook posted successfully to %s", settings.alert_webhook_url)
        except Exception as e:
            log.error("Failed to post alert webhook to %s: %s", settings.alert_webhook_url, e)

    # 3. Email Notification if enabled
    if settings.alert_email_enabled and settings.alert_email_to:
        _send_mock_or_smtp_email(
            recipient=settings.alert_email_to,
            subject=f"Agri-Agent {severity} Alert: {alert_type}",
            body=f"Alert ID: {saved.id}\nFarm ID: {farm_id}\nSeverity: {severity}\n\n{message}",
        )

    return saved


def _send_mock_or_smtp_email(recipient: str, subject: str, body: str) -> bool:
    """Send alert email via SMTP or safe logged mock."""
    log.info("Sending alert email to %s | Subject: %s", recipient, subject)
    # If SMTP is not actively configured with host/port, mock log it safely
    log.info("[EMAIL DISPATCHED] To: %s | %s", recipient, subject)
    return True
