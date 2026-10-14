import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from agent.prompts import SYSTEM
from tools import find_failed_login_spikes, search_logs, get_user_timeline, check_ip_reputation
import json, pathlib


import time

load_dotenv(override=True)
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
MAX_STEPS = 10
FALLBACKS = list(dict.fromkeys([MODEL]))
CACHE = pathlib.Path(__file__).resolve().parent.parent / "data" / "last_run.json"

TOOLS = {f.__name__: f for f in
         (find_failed_login_spikes, search_logs, get_user_timeline, check_ip_reputation)}

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
config = types.GenerateContentConfig(
    system_instruction=SYSTEM,
    tools=list(TOOLS.values()),
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

def _investigate_live(question: str):
    """Runs the agent loop. Yields events so a UI can show each step live."""
    contents = [types.Content(role="user", parts=[types.Part(text=question)])]
    for step in range(1, MAX_STEPS + 1):
        resp = _generate(contents)
        msg = resp.candidates[0].content
        contents.append(msg)                      # keep the model's turn exactly as returned
        calls = [p.function_call for p in (msg.parts or []) if p.function_call]
        if not calls:
            text = "".join(p.text for p in (msg.parts or []) if p.text)
            yield {"type": "final", "step": step, "text": text}
            return
        results = []
        for c in calls:
            args = dict(c.args or {})
            yield {"type": "tool_call", "step": step, "name": c.name, "args": args}
            try:
                out = TOOLS[c.name](**args)
            except Exception as e:
                out = {"error": str(e)}
            yield {"type": "tool_result", "step": step, "name": c.name, "result": out}
            results.append(types.Part.from_function_response(name=c.name, response={"result": out}))
        contents.append(types.Content(role="user", parts=results))
    yield {"type": "final", "step": MAX_STEPS, "text": "Stopped: reached the step limit."}

def investigate(question: str):
    events = []
    try:
        for ev in _investigate_live(question):
            events.append(ev)
            yield ev
        CACHE.write_text(json.dumps(events, default=str))   # save after a full successful run
    except RuntimeError:
        if events or not CACHE.exists():
            raise                                           # failed mid-run, or nothing saved yet
        for ev in json.loads(CACHE.read_text()):            # API down: replay the last good run
            yield ev

def _generate(contents):
    last = None
    for model in FALLBACKS:
        for attempt in range(5):
            try:
                return client.models.generate_content(model=model, contents=contents, config=config)
            except Exception as e:
                last = e
                s = str(e)
                if "404" in s or "NOT_FOUND" in s:
                    break                          # model not usable, try the next one
                if "503" in s or "UNAVAILABLE" in s or "429" in s:
                    time.sleep(min(2 ** attempt, 16))   # 1, 2, 4, 8, 16 seconds
                    continue
                raise
    raise RuntimeError(f"All models unavailable. Last error: {last}")

if __name__ == "__main__":
    q = "Was there a security breach last night? Investigate the logs."
    for ev in investigate(q):
        if ev["type"] == "tool_call":
            print(f"\n[step {ev['step']}] calling {ev['name']} {ev['args']}")
        elif ev["type"] == "tool_result":
            print("   result:", str(ev["result"])[:300])
        else:
            print("\n=== REPORT ===\n" + ev["text"])
