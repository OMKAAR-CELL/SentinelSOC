import os
from dotenv import load_dotenv
from google import genai
print("Hello World!")
load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
r = client.models.generate_content(model="gemini-3.8-flash", contents="Say hello in 5 words")
print(r.text)
