import asyncio
from nodes import actuator_node

async def main():
    try:
        res = await actuator_node({"human_approved": True, "decision": "irrigate", "crop_type": "Wheat", "latitude": 35.0, "longitude": -0.6, "water_salinity": 1.2, "water_volume_liters": 1000, "thread_id": "test-123"})
        print("Actuator result:", res)
    except Exception as e:
        print("Actuator error!")
        import traceback
        traceback.print_exc()

asyncio.run(main())
