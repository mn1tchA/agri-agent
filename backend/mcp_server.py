"""
MCP (Model Context Protocol) Server — Agri Irrigation Actuator.

Exposes simulated irrigation hardware control tools as MCP-compliant callable tools,
implementing the Model Context Protocol standard for agent-hardware interfacing.

Usage:
    Standalone MCP server (stdio — for IDE/agent integration):
        python mcp_server.py

    In-process via FastMCP Client (used by actuator_node):
        from mcp_server import mcp as irrigation_mcp
        from fastmcp import Client
        async with Client(irrigation_mcp) as client:
            result = await client.call_tool("irrigate_valve", {...})
"""

import logging
from datetime import UTC, datetime

from fastmcp import FastMCP

# Ensure FastMCP FunctionTool instances remain callable like normal Python functions
try:
    from fastmcp.tools import FunctionTool

    if "__call__" not in FunctionTool.__dict__:
        FunctionTool.__call__ = lambda self, *args, **kwargs: self.fn(*args, **kwargs)  # type: ignore[method-assign]
except Exception:
    pass

from database import (
    ValveCommand,
    emergency_stop_all_valves,
    get_valve_command,
    list_valve_commands,
    save_valve_command,
)

log = logging.getLogger("agri_agent.mcp_server")

# ---------------------------------------------------------------------------
# FastMCP Server Definition
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="agri-irrigation-actuator",
    instructions=(
        "MCP server exposing simulated irrigation hardware control tools for the Agri-Agent Swarm. "
        "Use irrigate_valve to dispatch water volume commands to field valve controllers, "
        "get_valve_status to query the hardware state of a previously issued command, "
        "and emergency_stop to immediately halt all active irrigation valves."
    ),
)


# ---------------------------------------------------------------------------
# Tool 1 — irrigate_valve
# ---------------------------------------------------------------------------
@mcp.tool()
def irrigate_valve(
    crop_type: str,
    volume_liters: float,
    latitude: float,
    longitude: float,
    water_salinity: float,
    thread_id: str,
    farm_id: int | None = None,
) -> dict:
    """
    Dispatch an irrigation command to the field valve controller and persist in DB.

    Args:
        crop_type: The crop being irrigated (e.g., 'Wheat', 'Tomato', 'Potato').
        volume_liters: Exact volume of water to dispatch in liters. Must be > 0.
        latitude: Farm latitude coordinate (decimal degrees, -90 to 90).
        longitude: Farm longitude coordinate (decimal degrees, -180 to 180).
        water_salinity: Water salinity in dS/m for valve mixing calibration.
                        Values > 4.0 dS/m trigger dilution protocol.
        thread_id: Unique pipeline run identifier for audit log tracing.
        farm_id: Optional ID of the farm owning the valve.

    Returns:
        Hardware acknowledgement dict with status, command_id, and UTC timestamp.
    """
    now = datetime.now(UTC)
    command_id = f"CMD-{thread_id[:8].upper()}-{int(now.timestamp())}"
    dilution = "ACTIVE" if water_salinity > 4.0 else "INACTIVE"

    valve_record = ValveCommand(
        command_id=command_id,
        thread_id=thread_id,
        farm_id=farm_id,
        crop_type=crop_type,
        command="OPEN_VALVE",
        volume_dispatched_liters=round(volume_liters, 2),
        target_coordinates=f"({latitude:.4f}, {longitude:.4f})",
        water_salinity_ds_m=water_salinity,
        dilution_protocol=dilution,
        status="EXECUTED",
        hardware_ack="VALVE_OPENED_OK",
        timestamp_utc=now,
    )
    save_valve_command(valve_record)

    log.info(
        "MCP irrigate_valve (persisted) | id=%s | %.0fL → %s | salinity=%.1f dS/m",
        command_id,
        volume_liters,
        valve_record.target_coordinates,
        water_salinity,
    )
    return {
        "status": "EXECUTED",
        "command_id": command_id,
        "command": "OPEN_VALVE",
        "crop_type": crop_type,
        "volume_dispatched_liters": round(volume_liters, 2),
        "target_coordinates": valve_record.target_coordinates,
        "water_salinity_ds_m": water_salinity,
        "dilution_protocol": dilution,
        "timestamp_utc": now.isoformat(),
        "hardware_ack": "VALVE_OPENED_OK",
        "farm_id": farm_id,
    }


# ---------------------------------------------------------------------------
# Tool 2 — get_valve_status
# ---------------------------------------------------------------------------
@mcp.tool()
def get_valve_status(command_id: str) -> dict:
    """
    Query the current status of a previously issued valve command from SQLite.

    Args:
        command_id: The command ID returned by irrigate_valve (e.g., 'CMD-A1B2C3D4-...').

    Returns:
        Current hardware status record or NOT_FOUND dict.
    """
    record = get_valve_command(command_id)
    if record:
        return {
            "status": record.status,
            "command_id": record.command_id,
            "command": record.command,
            "crop_type": record.crop_type,
            "volume_dispatched_liters": record.volume_dispatched_liters,
            "target_coordinates": record.target_coordinates,
            "water_salinity_ds_m": record.water_salinity_ds_m,
            "dilution_protocol": record.dilution_protocol,
            "hardware_ack": record.hardware_ack,
            "timestamp_utc": record.timestamp_utc.isoformat(),
            "valve_state": "OPEN" if record.status == "EXECUTED" else "CLOSED",
            "farm_id": record.farm_id,
            "query_time_utc": datetime.now(UTC).isoformat(),
        }
    return {
        "status": "NOT_FOUND",
        "command_id": command_id,
        "message": "No record found. Command may have expired or ID is incorrect.",
    }


# ---------------------------------------------------------------------------
# Tool 3 — emergency_stop
# ---------------------------------------------------------------------------
@mcp.tool()
def emergency_stop(reason: str, thread_id: str) -> dict:
    """
    Issue an emergency stop, immediately closing all active irrigation valves in DB.

    Args:
        reason: Human-readable explanation for compliance logging.
        thread_id: Pipeline run ID triggering the stop.

    Returns:
        Emergency stop acknowledgement dict.
    """
    timestamp = datetime.now(UTC).isoformat()
    affected_count = emergency_stop_all_valves()
    recent = list_valve_commands(limit=20)
    affected_ids = [v.command_id for v in recent if v.status == "STOPPED"]

    log.warning(
        "MCP EMERGENCY_STOP | thread=%s | reason=%s | valves_closed=%d",
        thread_id[:8],
        reason,
        affected_count,
    )
    return {
        "status": "EMERGENCY_STOP_EXECUTED",
        "all_valves": "CLOSED",
        "valves_affected": affected_ids,
        "valves_closed_count": affected_count,
        "reason": reason,
        "thread_id": thread_id,
        "timestamp_utc": timestamp,
    }


# ---------------------------------------------------------------------------
# Tool 4 — list_recent_valves
# ---------------------------------------------------------------------------
@mcp.tool()
def list_recent_valves(farm_id: int | None = None, limit: int = 20) -> list[dict]:
    """List recent valve commands persisted in the SQLite database."""
    valves = list_valve_commands(farm_id=farm_id, limit=limit)
    return [
        {
            "command_id": v.command_id,
            "crop_type": v.crop_type,
            "volume_dispatched_liters": v.volume_dispatched_liters,
            "status": v.status,
            "target_coordinates": v.target_coordinates,
            "timestamp_utc": v.timestamp_utc.isoformat(),
            "farm_id": v.farm_id,
        }
        for v in valves
    ]


# ---------------------------------------------------------------------------
# Entrypoint — standalone stdio MCP server
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log.info("Starting Agri Irrigation Actuator MCP server (stdio transport)...")
    mcp.run()
