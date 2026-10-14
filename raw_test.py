import os, requests
from dotenv import load_dotenv
load_dotenv(override=True)

k = os.environ["GEMINI_API_KEY"]
r = requests.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    headers={"x-goog-api-key": k},
)
print(r.status_code)
print(r.text[:300])