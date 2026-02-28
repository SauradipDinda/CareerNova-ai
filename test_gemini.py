import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test():
    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    r = requests.get(url)
    print(r.status_code)
    for model in r.json().get("models", []):
        print(model["name"])

test()
