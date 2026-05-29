from fastapi.testclient import TestClient
from api import app
import json

with TestClient(app) as client:
    print("Testing analyze...")
    res = client.post("/api/analyze", json={"crop_type": "Wheat"}, stream=True)
    thread_id = None
    for line in res.iter_lines():
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                thread_id = data.get("thread_id")
            except:
                pass
    print("Thread ID:", thread_id)
    if thread_id:
        print("Testing actuate...")
        res2 = client.post("/api/actuate", json={"thread_id": thread_id, "is_approved": True})
        print(res2.status_code)
        if res2.status_code != 200:
            print("Error response:", res2.text)
