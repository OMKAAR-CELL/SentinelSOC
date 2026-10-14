import os
from dotenv import load_dotenv
from google import genai


import os
from dotenv import load_dotenv
load_dotenv(override=True)

k = os.environ.get("GEMINI_API_KEY", "")
print("GEMINI_API_KEY prefix:", repr(k[:6]), "| length:", len(k))
print("has quotes/spaces/newline:", any(c in k for c in "\"' \n\r"))
g = os.environ.get("GOOGLE_API_KEY", "")
print("GOOGLE_API_KEY prefix:", repr(g[:6]), "| length:", len(g))
print("Hello World!")
load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
r = client.models.generate_content(model="gemini-3.8-flash", contents="Say hello in 5 words")
print(r.text)
