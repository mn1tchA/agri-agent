"""
CLI test entry point for the Agri-Agent Swarm.
Runs the multi-agent pipeline locally and simulates human approval.

Usage:
    python main.py
"""
import asyncio
import logging
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from graph import create_workflow
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("agri_agent.main")


async def main():
    log.info("Starting Agri-Agent Swarm CLI test")

    async with AsyncSqliteSaver.from_conn_string(settings.sqlite_checkpoints_db) as checkpointer:
        workflow = create_workflow()
        app = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_approval_gate"],
        )

        config = {"configurable": {"thread_id": "cli_test_swarm_v2"}}

        # Initial state — all parameters configurable
        initial_state = {
            "crop_type": "Corn",
            "farm_area_sqm": 25_000.0,
            "target_moisture_threshold": 15.0,
            "latitude": settings.default_latitude,
            "longitude": settings.default_longitude,
            "water_salinity": 1.2,
            "plant_growth_stage": "Vegetative Stage (High Water Demand)",
        }

        log.info("--- Phase 1: Starting Execution ---")
        async for s in app.astream(initial_state, config=config, stream_mode="values"):
            if s.get("decision") and not s.get("human_approved"):
                log.info("SWARM PAUSED — Decision: %s | Volume: %.0fL | Cost: %.2f DZD",
                         s.get("decision"), s.get("water_volume_liters", 0),
                         s.get("financial_cost_dzd", 0))
                break

        log.info("--- Phase 2: Simulating Human Approval ---")
        await app.aupdate_state(config, {"human_approved": True})

        log.info("--- Phase 3: Resuming Execution ---")
        final_result = await app.ainvoke(None, config=config)
        log.info("FINAL RESULT: %s", final_result.get("actuator_message"))


if __name__ == "__main__":
    asyncio.run(main())