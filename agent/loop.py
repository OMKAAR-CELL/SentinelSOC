import os, json
from dotenv import load_dotenv
from groq import Groq
from agent.prompts import SYSTEM
from tools import find_failed_login_spikes, search_logs, get_user_timeline, check_ip_reputation

load_dotenv(override=True)
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_STEPS = 10

TOOLS = {f.__name__: f for f in
         (find_failed_login_spikes, search_logs, get_user_timeline, check_ip_reputation)}

client = Groq(api_key=os.environ["GROQ_API_KEY"])

def _fn(name, desc, props, required=()):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": list(required)}}}

S = {"type": "string"}
I = {"type": "integer"}
SCHEMAS = [
    _fn("find_failed_login_spikes", "Find IP and username pairs with many failed logins. Use this first to spot brute-force attacks.",
        {"min_count": I}),
    _fn("search_logs", "Search log events. source is auth, web or db. start and end are ISO times like 2026-10-12T02:00:00.",
        {"ip": S, "user": S, "source": S, "status": S, "start": S, "end": S, "limit": I}),
    _fn("get_user_timeline", "Get a user's important events: logins, db queries and exports, in time order.",
        {"user": S, "start": S, "end": S}, ["user"]),
    _fn("check_ip_reputation", "Check whether an IP address is known to be malicious.",
        {"ip": S}, ["ip"]),
]

def investigate(question: str):
    """Runs the agent loop. Yields events so a UI can show each step live."""
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    for step in range(1, MAX_STEPS + 1):
        last = step == MAX_STEPS
        if last:
            messages.append({"role": "user", "content": "Step limit reached. Do not call more tools. Write the final incident report now from the evidence gathered."})
        resp = client.chat.completions.create(model=MODEL, messages=messages, tools=SCHEMAS,
                                              tool_choice="none" if last else "auto", temperature=0.2)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            yield {"type": "final", "step": step, "text": msg.content or ""}
            return
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name,
                                                      "arguments": tc.function.arguments}}
                                        for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            for k in ("min_count", "limit"):
                if k in args:
                    args[k] = int(args[k])
            yield {"type": "tool_call", "step": step, "name": tc.function.name, "args": args}
            try:
                out = TOOLS[tc.function.name](**args)
            except Exception as e:
                out = {"error": str(e)}
            yield {"type": "tool_result", "step": step, "name": tc.function.name, "result": out}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(out)[:6000]})
    yield {"type": "final", "step": MAX_STEPS, "text": "Stopped: reached the step limit."}

if __name__ == "__main__":
    for ev in investigate("Was there a security breach last night? Investigate the logs."):
        if ev["type"] == "tool_call":
            print(f"\n[step {ev['step']}] calling {ev['name']} {ev['args']}")
        elif ev["type"] == "tool_result":
            print("   result:", str(ev["result"])[:300])
        else:
            print("\n=== REPORT ===\n" + ev["text"])
