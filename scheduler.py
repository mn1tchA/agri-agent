"""
Scheduled background analysis for the Agri-Agent Swarm using APScheduler.

Periodically monitors registered farms, queries live Open-Meteo telemetry,
detects anomalies, and triggers proactive alerts.
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx

from config import settings
from database import list_farms_for_user, Farm
from alerting import dispatch_alert

log = logging.getLogger("agri_agent.scheduler")

scheduler = AsyncIOScheduler()


async def check_single_farm(farm: Farm) -> dict:
    """
    Fetch telemetry for a farm, evaluate anomaly & moisture rules, and alert if needed.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={farm.latitude}&longitude={farm.longitude}"
        f"&current=temperature_2m,relative_humidity_2m,soil_moisture_0_to_1cm"
    )

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json().get("current", {})
                temp = float(data.get("temperature_2m", 25.0))
                raw_moisture = float(data.get("soil_moisture_0_to_1cm", 0.15))
                # Open-Meteo returns m³/m³; convert to percentage if < 1.0
                soil_moisture = raw_moisture * 100.0 if raw_moisture < 1.0 else raw_moisture
            else:
                temp = 25.0
                soil_moisture = 15.0
    except Exception as e:
        log.warning("Scheduler: failed to fetch live telemetry for farm #%s: %s", farm.id, e)
        temp = 25.0
        soil_moisture = 15.0

    alerts_triggered = []

    # Rule 1: Extreme heat anomaly
    if temp > 45.0:
        alert = await dispatch_alert(
            farm_id=farm.id,
            alert_type="EXTREME_HEAT",
            severity="CRITICAL",
            message=f"Critical temperature anomaly on farm '{farm.name}': {temp:.1f}°C (Threshold: 45°C).",
        )
        alerts_triggered.append(alert.id)

    # Rule 2: Sensor flooding anomaly
    if soil_moisture > 92.0:
        alert = await dispatch_alert(
            farm_id=farm.id,
            alert_type="SENSOR_FLOODING",
            severity="CRITICAL",
            message=f"Soil moisture reading exceeds safety bounds on farm '{farm.name}': {soil_moisture:.1f}% > 92%.",
        )
        alerts_triggered.append(alert.id)

    # Rule 3: Salinity spike
    if farm.water_salinity > 8.0:
        alert = await dispatch_alert(
            farm_id=farm.id,
            alert_type="SALINITY_SPIKE",
            severity="CRITICAL",
            message=f"Dangerous water salinity detected on farm '{farm.name}': {farm.water_salinity:.1f} dS/m (Threshold: 8.0).",
        )
        alerts_triggered.append(alert.id)

    # Rule 4: Irrigation deficit reminder
    if soil_moisture < farm.moisture_threshold:
        alert = await dispatch_alert(
            farm_id=farm.id,
            alert_type="MOISTURE_DEFICIT",
            severity="WARNING",
            message=(
                f"Soil moisture on farm '{farm.name}' is {soil_moisture:.1f}%, "
                f"below target threshold of {farm.moisture_threshold:.1f}%. Analysis recommended."
            ),
        )
        alerts_triggered.append(alert.id)

    return {
        "farm_id": farm.id,
        "farm_name": farm.name,
        "temperature": temp,
        "soil_moisture": soil_moisture,
        "alerts_triggered": len(alerts_triggered),
    }


async def run_scheduled_farm_check() -> list[dict]:
    """Inspect all registered farms in the system."""
    log.info("Running scheduled farm health & anomaly check...")
    farms = list_farms_for_user()
    results = []
    for farm in farms:
        res = await check_single_farm(farm)
        results.append(res)
    log.info("Scheduled farm check completed across %d farms.", len(results))
    return results


def start_scheduler() -> None:
    """Start the APScheduler background worker."""
    if not settings.scheduler_enabled:
        log.info("APScheduler is disabled by configuration (SCHEDULER_ENABLED=False)")
        return

    if not scheduler.running:
        scheduler.add_job(
            run_scheduled_farm_check,
            "interval",
            minutes=settings.scheduler_interval_minutes,
            id="periodic_farm_check",
            replace_existing=True,
        )
        scheduler.start()
        log.info(
            "APScheduler started (periodic farm check interval: %d min)",
            settings.scheduler_interval_minutes,
        )


def stop_scheduler() -> None:
    """Gracefully shut down the APScheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("APScheduler stopped")
