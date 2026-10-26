"""
Unit and integration tests for the MCP Irrigation Actuator server and database persistence.
"""

import pytest

from database import (
    create_db_and_tables,
    get_valve_command,
)
from mcp_server import emergency_stop, get_valve_status, irrigate_valve, list_recent_valves


@pytest.fixture(autouse=True)
def init_db():
    create_db_and_tables()


class TestMCPIrrigationActuator:
    """Test MCP tool executions and SQLite persistence."""

    def test_irrigate_valve_persists_in_db(self):
        result = irrigate_valve(
            crop_type="Potato",
            volume_liters=12500.0,
            latitude=35.69,
            longitude=-0.63,
            water_salinity=1.5,
            thread_id="test-mcp-thread-1",
            farm_id=1,
        )
        assert result["status"] == "EXECUTED"
        assert result["volume_dispatched_liters"] == 12500.0
        assert "CMD-TEST-MCP" in result["command_id"]
        assert result["dilution_protocol"] == "INACTIVE"

        # Verify persisted in SQLite
        db_record = get_valve_command(result["command_id"])
        assert db_record is not None
        assert db_record.crop_type == "Potato"
        assert db_record.volume_dispatched_liters == 12500.0
        assert db_record.status == "EXECUTED"

    def test_irrigate_valve_high_salinity_triggers_dilution(self):
        result = irrigate_valve(
            crop_type="Tomato",
            volume_liters=8000.0,
            latitude=35.70,
            longitude=-0.60,
            water_salinity=5.5,
            thread_id="test-mcp-thread-2",
        )
        assert result["dilution_protocol"] == "ACTIVE"
        db_record = get_valve_command(result["command_id"])
        assert db_record is not None
        assert db_record.dilution_protocol == "ACTIVE"

    def test_get_valve_status_found(self):
        res = irrigate_valve(
            crop_type="Wheat",
            volume_liters=5000.0,
            latitude=35.69,
            longitude=-0.63,
            water_salinity=1.0,
            thread_id="test-mcp-thread-3",
        )
        status_res = get_valve_status(res["command_id"])
        assert status_res["status"] == "EXECUTED"
        assert status_res["command_id"] == res["command_id"]
        assert status_res["valve_state"] == "OPEN"

    def test_get_valve_status_not_found(self):
        status_res = get_valve_status("NON_EXISTENT_CMD_999")
        assert status_res["status"] == "NOT_FOUND"

    def test_emergency_stop_halts_valves(self):
        # Dispatch two valves
        res1 = irrigate_valve(
            crop_type="Wheat",
            volume_liters=2000.0,
            latitude=35.69,
            longitude=-0.63,
            water_salinity=1.0,
            thread_id="thread-stop-1",
        )
        res2 = irrigate_valve(
            crop_type="Barley",
            volume_liters=3000.0,
            latitude=35.69,
            longitude=-0.63,
            water_salinity=1.0,
            thread_id="thread-stop-2",
        )

        stop_res = emergency_stop(
            reason="Heatwave emergency override",
            thread_id="thread-stop-trigger",
        )
        assert stop_res["status"] == "EMERGENCY_STOP_EXECUTED"
        assert stop_res["all_valves"] == "CLOSED"
        assert stop_res["valves_closed_count"] >= 2

        # Check DB state
        rec1 = get_valve_command(res1["command_id"])
        rec2 = get_valve_command(res2["command_id"])
        assert rec1.status == "STOPPED"
        assert rec2.status == "STOPPED"

    def test_list_recent_valves(self):
        irrigate_valve(
            crop_type="Wheat",
            volume_liters=1000.0,
            latitude=35.69,
            longitude=-0.63,
            water_salinity=1.0,
            thread_id="list-thread-1",
        )
        valves = list_recent_valves(limit=10)
        assert len(valves) >= 1
        assert "command_id" in valves[0]
