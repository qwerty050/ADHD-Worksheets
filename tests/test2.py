import requests
import json

payload = {
    "model": "gpt-oss:120b-cloud",
    "prompt": "Target Slide Content:\n[Cannot decode W5M1.pdf as text.]\n",
    "system": "You are an academic extraction agent.",
    "stream": False,
    "format": "json"
}

try:
    response = requests.post("http://localhost:11434/api/generate", json=payload)
    print("Status:", response.status_code)
    print("Text:", response.text)
except Exception as e:
    print("Error:", e)
