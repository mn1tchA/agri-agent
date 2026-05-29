import requests
import json

res = requests.post('http://localhost:8888/api/analyze', json={'crop_type': 'Wheat'})
print('analyze status:', res.status_code)
thread_id = None
for line in res.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            data = json.loads(line[6:])
            thread_id = data.get('thread_id')
            break

print('thread_id:', thread_id)
if thread_id:
    res2 = requests.post('http://localhost:8888/api/actuate', json={'thread_id': thread_id, 'is_approved': True})
    print('actuate status:', res2.status_code)
    print('actuate body:', res2.text)
