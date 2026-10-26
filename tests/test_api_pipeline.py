"""
Integration tests for the full FastAPI pipeline, authentication, multi-tenancy,
observability, and valve tracking endpoints.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from api import app
from config import settings
from database import create_db_and_tables, Farm, create_farm, DecisionLog, save_decision_log


@pytest.fixture(autouse=True)
def setup_database():
    create_db_and_tables()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
class TestAuthPipeline:
    """Tests for authentication and token validation."""

    async def test_login_valid_operator(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/auth/token",
                data={"username": settings.admin_username, "password": settings.admin_password},
            )
            assert res.status_code == 200
            data = res.json()
            assert "access_token" in data
            assert data["role"] == "operator"

    async def test_login_valid_viewer(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/auth/token",
                data={"username": settings.viewer_username, "password": settings.viewer_password},
            )
            assert res.status_code == 200
            data = res.json()
            assert "access_token" in data
            assert data["role"] == "viewer"

    async def test_login_invalid_password(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/auth/token",
                data={"username": settings.admin_username, "password": "wrong_password_xyz"},
            )
            assert res.status_code == 401


@pytest.mark.asyncio
class TestHealthAndObservabilityEndpoints:
    """Tests for health check, Prometheus /metrics, and LangSmith diagnostics."""

    async def test_health_check(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/health")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "healthy"
            assert "version" in data

    async def test_prometheus_metrics_endpoint(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/metrics")
            assert res.status_code == 200
            assert "agri_" in res.text or "python_" in res.text

    async def test_langsmith_diagnostics(self):
        from security import create_access_token
        token = create_access_token({"sub": settings.viewer_username, "role": "viewer"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get(
                "/api/v1/observability/langsmith",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            data = res.json()
            assert "project" in data
            assert "endpoint" in data


@pytest.mark.asyncio
class TestMultiTenancyFarms:
    """Tests for Farm management and role-based permissions."""

    async def test_farm_lifecycle(self):
        from security import create_access_token
        op_token = create_access_token({"sub": settings.admin_username, "role": "operator"})
        view_token = create_access_token({"sub": settings.viewer_username, "role": "viewer"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Viewer tries to create farm -> 403 Forbidden
            res = await ac.post(
                "/api/v1/farms",
                json={"name": "Forbidden Farm", "crop_type": "Tomato"},
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert res.status_code == 403

            # 2. Operator creates farm -> 200 OK
            res = await ac.post(
                "/api/v1/farms",
                json={
                    "name": "Biskra Date Palms",
                    "crop_type": "Date Palm",
                    "farm_area_sqm": 25000.0,
                    "latitude": 34.85,
                    "longitude": 5.73,
                    "moisture_threshold": 8.0,
                    "water_salinity": 2.1,
                },
                headers={"Authorization": f"Bearer {op_token}"},
            )
            assert res.status_code == 200
            farm_data = res.json()
            farm_id = farm_data["id"]
            assert farm_data["name"] == "Biskra Date Palms"

            # 3. Viewer lists farms -> 200 OK
            res = await ac.get(
                "/api/v1/farms",
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert res.status_code == 200
            farms = res.json()
            assert any(f["id"] == farm_id for f in farms)

            # 4. Get single farm
            res = await ac.get(
                f"/api/v1/farms/{farm_id}",
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert res.status_code == 200
            assert res.json()["crop_type"] == "Date Palm"

            # 5. Update farm
            res = await ac.put(
                f"/api/v1/farms/{farm_id}",
                json={"moisture_threshold": 9.5},
                headers={"Authorization": f"Bearer {op_token}"},
            )
            assert res.status_code == 200
            assert res.json()["moisture_threshold"] == 9.5


@pytest.mark.asyncio
class TestValvesAndAlertsEndpoints:
    """Tests for valve monitoring and alert management."""

    async def test_valves_and_emergency_stop(self):
        from security import create_access_token
        op_token = create_access_token({"sub": settings.admin_username, "role": "operator"})
        view_token = create_access_token({"sub": settings.viewer_username, "role": "viewer"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # List valves
            res = await ac.get(
                "/api/v1/valves",
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert res.status_code == 200
            assert isinstance(res.json(), list)

            # Persist a valve command and query it
            from mcp_server import irrigate_valve
            valve_ack = irrigate_valve(
                crop_type="Wheat",
                volume_liters=3000.0,
                latitude=35.69,
                longitude=-0.63,
                water_salinity=1.0,
                thread_id="test-valve-api-thread",
            )
            v_res = await ac.get(
                f"/api/v1/valves/{valve_ack['command_id']}",
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert v_res.status_code == 200
            assert v_res.json()["command_id"] == valve_ack["command_id"]

            # Trigger emergency stop
            res = await ac.post(
                "/api/v1/valves/emergency-stop",
                headers={"Authorization": f"Bearer {op_token}"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "success"

    async def test_alerts_and_acknowledgement(self):
        from security import create_access_token
        from alerting import dispatch_alert
        view_token = create_access_token({"sub": settings.viewer_username, "role": "viewer"})

        # Dispatch test alert
        alert = await dispatch_alert(
            message="Salinity spike warning",
            severity="CRITICAL",
            alert_type="SALINITY_SPIKE",
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get(
                "/api/v1/alerts",
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert res.status_code == 200
            alerts = res.json()
            assert any(a["id"] == alert.id for a in alerts)

            # Ack alert
            res = await ac.post(
                f"/api/v1/alerts/{alert.id}/ack",
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert res.status_code == 200
            assert res.json()["alert_id"] == alert.id


@pytest.mark.asyncio
class TestAnalyticsAndFeedback:
    """Tests for history, stats, and outcome feedback."""

    async def test_history_and_stats(self):
        from security import create_access_token
        view_token = create_access_token({"sub": settings.viewer_username, "role": "viewer"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get(
                "/api/v1/history",
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert res.status_code == 200
            assert "history" in res.json()

            res = await ac.get(
                "/api/v1/stats",
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert res.status_code == 200
            assert "total_decisions" in res.json()

    async def test_feedback_submission(self):
        from security import create_access_token
        view_token = create_access_token({"sub": settings.viewer_username, "role": "viewer"})

        # Save a test decision log
        log_entry = DecisionLog(
            thread_id="thread-feedback-test",
            crop_type="Wheat",
            temperature=26.0,
            soil_moisture=14.0,
            water_salinity=1.0,
            decision="irrigate",
            water_volume_liters=4000.0,
            financial_cost_dzd=600.0,
            human_approved=True,
        )
        saved = save_decision_log(log_entry)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/feedback",
                json={"log_id": saved.id, "rating": 5},
                headers={"Authorization": f"Bearer {view_token}"},
            )
            assert res.status_code == 200
            assert res.json()["rating"] == 5

            # Test compat feedback
            compat_res = await ac.post(
                "/api/feedback",
                json={"log_id": saved.id, "rating": 4},
            )
            assert compat_res.status_code == 200

            # Test compat history & stats
            assert (await ac.get("/api/history")).status_code == 200
            assert (await ac.get("/api/stats")).status_code == 200

    async def test_scheduler_run_and_farm_deletion(self):
        from security import create_access_token
        admin_token = create_access_token({"sub": settings.admin_username, "role": "admin"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Trigger scheduler run-now
            res = await ac.post(
                "/api/v1/scheduler/run-now",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "success"

            # Create a disposable farm and delete it
            farm_res = await ac.post(
                "/api/v1/farms",
                json={"name": "Temporary Farm", "crop_type": "Oats"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            farm_id = farm_res.json()["id"]

            del_res = await ac.delete(
                f"/api/v1/farms/{farm_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert del_res.status_code == 200
