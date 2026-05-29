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
import json
import logging
from datetime import datetime, timezone

from fastmcp import FastMCP

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

# In-memory hardware state registry
# Production replacement: integrate with real PLC/SCADA REST API or OPC-UA endpoint
_valve_registry: dict[str, dict] = {}


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
) -> dict:
    """
    Dispatch an irrigation command to the field valve controller.

    Args:
        crop_type: The crop being irrigated (e.g., 'Wheat', 'Tomato', 'Potato').
        volume_liters: Exact volume of water to dispatch in liters. Must be > 0.
        latitude: Farm latitude coordinate (decimal degrees, -90 to 90).
        longitude: Farm longitude coordinate (decimal degrees, -180 to 180).
        water_salinity: Water salinity in dS/m for valve mixing calibration.
                        Values > 4.0 dS/m trigger dilution protocol.
        thread_id: Unique pipeline run identifier for audit log tracing.

    Returns:
        Hardware acknowledgement dict with status, command_id, and UTC timestamp.
        Example: {"status": "EXECUTED", "command_id": "CMD-A1B2C3D4-...", ...}
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    command_id = f"CMD-{thread_id[:8].upper()}-{int(datetime.now().timestamp())}"

    record = {
        "status": "EXECUTED",
        "command_id": command_id,
        "command": "OPEN_VALVE",
        "crop_type": crop_type,
        "volume_dispatched_liters": round(volume_liters, 2),
        "target_coordinates": f"({latitude:.4f}, {longitude:.4f})",
        "water_salinity_ds_m": water_salinity,
        "dilution_protocol": "ACTIVE" if water_salinity > 4.0 else "INACTIVE",
        "timestamp_utc": timestamp,
        "hardware_ack": "VALVE_OPENED_OK",
    }
    _valve_registry[command_id] = record
    log.info(
        "MCP irrigate_valve | id=%s | %.0fL → %s | salinity=%.1f dS/m",
        command_id, volume_liters, record["target_coordinates"], water_salinity,
    )
    return record


# ---------------------------------------------------------------------------
# Tool 2 — get_valve_status
# ---------------------------------------------------------------------------
@mcp.tool()
def get_valve_status(command_id: str) -> dict:
    """
    Query the current status of a previously issued valve command.

    Args:
        command_id: The command ID returned by irrigate_valve (e.g., 'CMD-A1B2C3D4-...').
                    Must be an exact match — partial IDs are not accepted.

    Returns:
        Current hardware status record including valve_state and query timestamp,
        or an error dict if the command_id is not found.
    """
    if command_id in _valve_registry:
        return {
            **_valve_registry[command_id],
            "valve_state": _valve_registry[command_id].get("valve_state", "OPEN"),
            "query_time_utc": datetime.now(timezone.utc).isoformat(),
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
    Issue an emergency stop, immediately closing all active irrigation valves.

    Use this when critical anomalies are confirmed by a human operator:
    extreme heat events, sensor failures, waterlogging, or critical salinity spikes.

    Args:
        reason: Human-readable explanation for the emergency stop (logged for compliance).
        thread_id: Pipeline run ID triggering the stop (for audit correlation).

    Returns:
        Emergency stop acknowledgement including list of affected valve command IDs.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    affected = list(_valve_registry.keys())
    for cmd_id in affected:
        _valve_registry[cmd_id]["valve_state"] = "EMERGENCY_CLOSED"

    log.warning(
        "MCP EMERGENCY_STOP | thread=%s | reason=%s | valves_closed=%d",
        thread_id[:8], reason, len(affected),
    )
    return {
        "status": "EMERGENCY_STOP_EXECUTED",
        "all_valves": "CLOSED",
        "valves_affected": affected,
        "valves_closed_count": len(affected),
        "reason": reason,
        "thread_id": thread_id,
        "timestamp_utc": timestamp,
    }


# ---------------------------------------------------------------------------
# Entrypoint — standalone stdio MCP server
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log.info("Starting Agri Irrigation Actuator MCP server (stdio transport)...")
    mcp.run()
