import streamlit as st
from datetime import datetime
from agent.loop import investigate
from tools import find_failed_login_spikes, block_ip

st.set_page_config(page_title="SentinelSOC", page_icon="🛡️", layout="wide")
st.title("🛡️ SentinelSOC")
st.caption("Autonomous SOC agent · JAI 2026 · Track 1: Agentic AI for Cybersecurity")

ss = st.session_state
ss.setdefault("events", [])
ss.setdefault("report", None)
ss.setdefault("ip", None)
ss.setdefault("log", [])
ss.setdefault("done", set())

level = st.sidebar.radio("Autonomy level",
                         ["Alert only", "Auto low-risk", "Ask before any action"], index=2)
st.sidebar.caption("Low-risk: alerts and watch list. High-risk: blocking an IP always needs a human unless you choose otherwise.")

def render_event(ev):
    if ev["type"] == "tool_call":
        st.markdown(f"**Step {ev['step']}** · calling `{ev['name']}` with `{ev['args']}`")
    elif ev["type"] == "tool_result":
        with st.expander(f"Result from {ev['name']}"):
            st.json(ev["result"])

question = st.text_input("Ask the agent", "Was there a security breach last night?")
c1, c2 = st.columns(2)
ask = c1.button("Investigate", type="primary")
scan = c2.button("Run watcher scan")

to_run = None
if ask:
    to_run = question
if scan:
    spikes = find_failed_login_spikes(100)
    if spikes:
        s = spikes[0]
        to_run = (f"ALERT from watcher rule: {s['failed']} failed logins for user '{s['user']}' "
                  f"from IP {s['ip']} between {s['first_seen']} and {s['last_seen']}. Investigate.")
        st.warning(f"Watcher rule fired: {s['failed']} failed logins from {s['ip']}. Waking the agent.")
    else:
        st.success("Watcher: all clear.")

st.subheader("Investigation")
steps = st.container()

if to_run:
    ss.events, ss.report, ss.ip, ss.log, ss.done = [], None, None, [], set()
    with st.spinner("Agent is investigating..."):
        for ev in investigate(to_run):
            ss.events.append(ev)
            if (ev["type"] == "tool_result" and ev["name"] == "find_failed_login_spikes"
                    and isinstance(ev["result"], list) and ev["result"] and not ss.ip):
                ss.ip = ev["result"][0]["ip"]
            if ev["type"] == "final":
                ss.report = ev["text"]
            with steps:
                render_event(ev)
else:
    with steps:
        for ev in ss.events:
            render_event(ev)

if ss.report:
    st.subheader("Incident report")
    st.markdown(ss.report)

if ss.report and ss.ip:
    st.subheader("Proposed actions")
    ACTIONS = [("Create alert for the security team", "low"),
               ("Add IP to watch list", "low"),
               ("Block IP at the firewall", "high")]

    def do(name):
        if name.startswith("Block"):
            block_ip(ss.ip)
        ss.log.append(f"{datetime.now():%H:%M:%S} · {name} · {ss.ip}")
        ss.done.add(name)

    for name, risk in ACTIONS:
        a, b = st.columns([4, 1])
        a.write(f"**{name}** · {risk} risk · `{ss.ip}`")
        if name in ss.done:
            b.success("Done")
        elif level == "Alert only":
            b.caption("Recommended only")
        elif risk == "low" and level == "Auto low-risk":
            do(name)
            b.success("Auto")
        elif b.button("Approve", key=name):
            do(name)
            st.rerun()

    if ss.log:
        st.subheader("Action log")
        for line in ss.log:
            st.write(line)