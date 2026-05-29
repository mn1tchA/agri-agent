"""
LangGraph workflow definition for the Agri-Agent Swarm.

Architecture (with anomaly detection + conditional fan-out/fan-in):

    data_aggregation
         │
    anomaly_check          ← inspects sensor readings for critical conditions
         │
    ┌────┴────────────────────────────────────┐
    │ (anomaly detected)                      │ (normal)
    ▼                                         ▼
human_approval_gate               parallel_agents_fanout   ← pass-through
                                       ┌─────┼─────┐
                                       │     │     │
                                 meteorologist botanist agronomist
                                       └─────┼─────┘
                                             ▼
                                         pedologist
                                       ┌─────┴─────┐
                                       ▼           ▼
                                   economist    harvest
                                       └─────┬─────┘
                                             ▼
                                       orchestrator
                                             │
                                      [route_decision]
                                           ├── "wait"     → END
                                           └── "irrigate" / "micro_irrigate" → human_approval_gate → actuator → END
"""
import logging
from langgraph.graph import StateGraph, END
from state import FarmState
from nodes import (
    data_aggregation_node,
    anomaly_check_node,
    parallel_agents_fanout,
    meteorologist_agent_node,
    botanist_agent_node,
    agronomist_agent_node,
    pedologist_agent_node,
    economist_agent_node,
    harvest_agent_node,
    orchestrator_node,
    actuator_node,
)

log = logging.getLogger("agri_agent.graph")


# ---------------------------------------------------------------------------
# Routing Functions
# ---------------------------------------------------------------------------

def route_decision(state: FarmState) -> str:
    """Route after the Orchestrator: irrigate/micro_irrigate → human gate, wait → END."""
    decision = state.get("decision", "wait")
    log.info("Routing decision: %s", decision)
    if decision in ("irrigate", "micro_irrigate"):
        return "human_approval_gate"
    return END


def route_after_anomaly_check(state: FarmState) -> str:
    """
    Route after anomaly detection:
      - Critical anomaly detected → human_approval_gate (bypass all LLM agents, zero wasted tokens)
      - Normal readings           → parallel_agents_fanout (fans out to meteorologist + botanist + agronomist)
    """
    if state.get("anomaly_detected"):
        log.warning("Anomaly routing: → human_approval_gate (LLM agents bypassed)")
        return "human_approval_gate"
    log.info("Anomaly routing: → parallel_agents_fanout (normal pipeline)")
    return "parallel_agents_fanout"


# ---------------------------------------------------------------------------
# HITL Gate Node
# ---------------------------------------------------------------------------

async def human_approval_gate(state: FarmState) -> dict:
    """
    Empty node acting as a LangGraph interrupt breakpoint.

    The graph serializes its full state to SQLite via AsyncSqliteSaver and pauses
    execution here until POST /api/actuate resumes it with human_approved=True/False.
    """
    return {}


# ---------------------------------------------------------------------------
# Workflow Factory
# ---------------------------------------------------------------------------

def create_workflow() -> StateGraph:
    """Build and return the compiled Agri-Agent workflow graph."""
    workflow = StateGraph(FarmState)

    # --- Register Nodes ---
    workflow.add_node("data_aggregation",      data_aggregation_node)
    workflow.add_node("anomaly_check",         anomaly_check_node)
    workflow.add_node("parallel_agents_fanout", parallel_agents_fanout)
    workflow.add_node("meteorologist",         meteorologist_agent_node)
    workflow.add_node("botanist",              botanist_agent_node)
    workflow.add_node("agronomist",            agronomist_agent_node)
    workflow.add_node("pedologist",            pedologist_agent_node)
    workflow.add_node("economist",             economist_agent_node)
    workflow.add_node("harvest",               harvest_agent_node)
    workflow.add_node("orchestrator",          orchestrator_node)
    workflow.add_node("human_approval_gate",   human_approval_gate)
    workflow.add_node("actuator",              actuator_node)

    # --- Entry Point ---
    workflow.set_entry_point("data_aggregation")

    # --- data_aggregation → anomaly_check (always) ---
    workflow.add_edge("data_aggregation", "anomaly_check")

    # --- Conditional: anomaly → HITL gate | normal → fan-out node ---
    workflow.add_conditional_edges(
        "anomaly_check",
        route_after_anomaly_check,
        {
            "parallel_agents_fanout": "parallel_agents_fanout",
            "human_approval_gate":    "human_approval_gate",
        },
    )

    # --- Fan-Out: parallel_agents_fanout → meteorologist, botanist, agronomist (parallel) ---
    workflow.add_edge("parallel_agents_fanout", "meteorologist")
    workflow.add_edge("parallel_agents_fanout", "botanist")
    workflow.add_edge("parallel_agents_fanout", "agronomist")

    # --- Fan-In: meteorologist, botanist, agronomist → pedologist (waits for all three) ---
    workflow.add_edge("meteorologist", "pedologist")
    workflow.add_edge("botanist",      "pedologist")
    workflow.add_edge("agronomist",    "pedologist")

    # --- Fan-Out: pedologist → economist, harvest (parallel) ---
    workflow.add_edge("pedologist", "economist")
    workflow.add_edge("pedologist", "harvest")

    # --- Fan-In: economist, harvest → orchestrator (waits for both) ---
    workflow.add_edge("economist", "orchestrator")
    workflow.add_edge("harvest",   "orchestrator")

    # --- Conditional routing after Orchestrator ---
    workflow.add_conditional_edges(
        "orchestrator",
        route_decision,
        {
            "human_approval_gate": "human_approval_gate",
            END: END,
        },
    )

    # --- Human approval gate → actuator → END ---
    workflow.add_edge("human_approval_gate", "actuator")
    workflow.add_edge("actuator", END)

    log.info(
        "Workflow graph compiled: anomaly detection + conditional fan-out + parallel agents"
    )
    return workflow
