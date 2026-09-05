"""One live call per tool. Usage: ASTERWISE_API_KEY=aw_... python scripts/smoke.py"""
import json
import os
import sys

from asterwise_langchain import AsterwiseToolkit

key = os.environ.get("ASTERWISE_API_KEY")
if not key:
    sys.exit("Set ASTERWISE_API_KEY")
tools = {t.name: t for t in AsterwiseToolkit(api_key=key).get_tools()}
calls = {
    "asterwise_natal_chart": {"date": "1985-11-12", "time": "06:45", "location": "Mumbai, India"},
    "asterwise_western_natal_chart": {"date": "1985-11-12", "time": "06:45", "location": "Mumbai, India"},
    "asterwise_matchmaking": {"person1_date": "1990-05-14", "person1_time": "07:20", "person1_location": "Pune, India", "person2_date": "1992-11-03", "person2_time": "22:45", "person2_location": "Jaipur, India"},
    "asterwise_panchanga": {"date": "2026-09-05", "location": "New Delhi, India"},
    "asterwise_numerology_profile": {"name": "Arjun Mehta", "date": "1990-05-14"},
}
for name, args in calls.items():
    out = json.loads(tools[name].invoke(args))
    keys = list(out)[:6]
    print(f"{name}: ok, {len(json.dumps(out))} bytes, keys {keys}")
