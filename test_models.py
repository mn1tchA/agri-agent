import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url)

if response.status_code == 200:
    print("Here are the models your API key can access:")
    for model in response.json().get('models', []):
        # Only print the name of the model to keep it clean
        print(model['name'].replace('models/', ''))
else:
    print(f"Error connecting to Google: {response.text}")