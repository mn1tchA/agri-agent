import asyncio
from config import settings
from graph import create_workflow
from database import create_db_and_tables
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import uuid
import api

async def main():
    create_db_and_tables()
    async with AsyncSqliteSaver.from_conn_string(settings.sqlite_checkpoints_db) as checkpointer:
        workflow = create_workflow()
        api.agent_app = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_approval_gate"],
        )
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        initial_state = {
            "crop_type": "Wheat",
            "farm_area_sqm": 10000,
            "target_moisture_threshold": 10,
            "latitude": 35,
            "longitude": -0.6,
            "water_salinity": 1.2,
            "plant_growth_stage": "Vegetative Stage",
        }
        
        print("Running initial...")
        async for _ in api.agent_app.astream(
            initial_state, config=config, stream_mode="values"
        ):
            pass
            
        print("Running actuate...")
        req = api.ApprovalRequest(thread_id=thread_id, is_approved=True)
        try:
            res = await api.execute_hardware(req)
            print("Actuate succeeded:", res)
        except Exception as e:
            print("Actuate failed!")
            import traceback
            traceback.print_exc()

asyncio.run(main())
