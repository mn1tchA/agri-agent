import subprocess
import time
import requests
import json
import sys

p = subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--port", "8889"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(5)

print("Running analyze...")
res = requests.post('http://localhost:8889/api/analyze', json={'crop_type': 'Wheat'})
thread_id = None
for line in res.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            data = json.loads(line[6:])
            thread_id = data.get('thread_id')
            break

print("Thread ID:", thread_id)
if thread_id:
    print("Running actuate...")
    res2 = requests.post('http://localhost:8889/api/actuate', json={'thread_id': thread_id, 'is_approved': True})
    print("Actuate status:", res2.status_code)

time.sleep(2)
p.terminate()
out, err = p.communicate()
print("STDOUT:\n", out.decode('utf-8', errors='ignore'))
print("STDERR:\n", err.decode('utf-8', errors='ignore'))
