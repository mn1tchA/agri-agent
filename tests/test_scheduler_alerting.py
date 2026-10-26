"""
Unit and integration tests for the Alerting and APScheduler surveillance system.
"""

import pytest

from alerting import dispatch_alert
from database import Farm, create_db_and_tables, get_alert_logs
from scheduler import check_single_farm, run_scheduled_farm_check


@pytest.fixture(autouse=True)
def setup_data():
    create_db_and_tables()


@pytest.mark.asyncio
class TestAlertingSystem:
    """Test alert persistence and channel dispatching."""

    async def test_dispatch_alert_persists_in_db(self):
        alert = await dispatch_alert(
            message="Test critical soil anomaly detected",
            severity="CRITICAL",
            alert_type="SENSOR_FLOOD",
            farm_id=1,
            channel="IN_APP",
        )
        assert alert.id is not None
        assert alert.message == "Test critical soil anomaly detected"
        assert alert.severity == "CRITICAL"
        assert alert.acknowledged is False

        logs = get_alert_logs(farm_id=1)
        assert any(entry.id == alert.id for entry in logs)

    async def test_scheduler_farm_check_normal(self):
        farm = Farm(
            name="Normal Farm",
            latitude=35.69,
            longitude=-0.63,
            moisture_threshold=10.0,
            water_salinity=1.2,
        )
        res = await check_single_farm(farm)
        assert "farm_name" in res
        assert "temperature" in res
        assert "soil_moisture" in res

    async def test_scheduler_farm_check_detects_salinity_anomaly(self):
        farm = Farm(
            name="Saline Farm",
            latitude=35.69,
            longitude=-0.63,
            moisture_threshold=10.0,
            water_salinity=9.5,  # > 8.0 dS/m threshold
        )
        res = await check_single_farm(farm)
        assert res["alerts_triggered"] >= 1

    async def test_scheduler_lifecycle_and_batch_check(self):
        from scheduler import start_scheduler, stop_scheduler

        start_scheduler()
        stop_scheduler()

        results = await run_scheduled_farm_check()
        assert isinstance(results, list)

    async def test_dispatch_alert_email_and_webhook(self, monkeypatch):
        from alerting import _send_mock_or_smtp_email
        from config import settings

        monkeypatch.setattr(settings, "alert_email_enabled", True)
        monkeypatch.setattr(settings, "alert_email_to", "farmer@test.dz")
        monkeypatch.setattr(settings, "alert_webhook_url", "http://invalid-test-webhook.local")

        alert = await dispatch_alert(
            message="Test email and webhook",
            severity="WARNING",
            alert_type="TEST_CHANNELS",
        )
        assert alert.id is not None
        assert _send_mock_or_smtp_email("test@example.com", "Test Subject", "Test Body") is True

    async def test_scheduler_extreme_heat_and_moisture_deficit(self):
        hot_dry_farm = Farm(
            name="Hot Dry Farm",
            latitude=35.69,
            longitude=-0.63,
            moisture_threshold=50.0,  # will trigger deficit if moisture < 50
            water_salinity=1.0,
        )
        res = await check_single_farm(hot_dry_farm)
        assert res["farm_name"] == "Hot Dry Farm"
        assert res["alerts_triggered"] >= 1
