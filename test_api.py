import requests
import json

print("Starting request...")
r = requests.post(
    'http://127.0.0.1:8000/api/analyze',
    json={'crop_type':'Wheat','farm_area_sqm':10000.0,'target_moisture_threshold':10.0},
    stream=True
)

print(f"Status Code: {r.status_code}")

for line in r.iter_lines():
    if line:
        decoded_line = line.decode('utf-8')
        if decoded_line.startswith('data: '):
            data = json.loads(decoded_line[6:])
            print("\n--- CHUNK ---")
            print(f"Decision: {data.get('decision')}")
            print(f"Meteorologist: {data.get('meteorologist_analysis')}")
            print(f"Botanist: {data.get('botanist_analysis')}")
            print(f"Financial: {data.get('financial_analysis')}")
