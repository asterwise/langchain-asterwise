# langchain-asterwise

LangChain tools for the [Asterwise](https://asterwise.com) astrology API. Five `StructuredTool`s over the official Python SDK:

| Tool | What it returns |
|---|---|
| `asterwise_natal_chart` | Vedic natal chart: planets by sign, degree, nakshatra and house; ascendant; Moon sign |
| `asterwise_western_natal_chart` | Western natal chart: planets, ascendant, midheaven; Placidus, Koch, Equal or Whole Sign |
| `asterwise_matchmaking` | Ashtakoot Guna Milan out of 36 with Rajju and Vedha as separate vetoes, Mangal dosha comparison, narrative |
| `asterwise_panchanga` | Tithi, nakshatra, yoga, karana, vara, sunrise and sunset, Rahu kaal for a date and place |
| `asterwise_numerology_profile` | Life path, expression, soul urge, personality and related numbers |

Outputs are slimmed by default to the fields a model needs to reason with. Pass `slim=False` for the full API payload. Birthplaces are plain text; the API geocodes them.

## Install

```bash
pip install langchain-asterwise
```

Get a free key at [asterwise.com/dashboard](https://asterwise.com/dashboard): 500 calls a month, no card.

## Use

```python
import os
from asterwise_langchain import AsterwiseToolkit

tools = AsterwiseToolkit(api_key=os.environ["ASTERWISE_API_KEY"]).get_tools()
```

With any LangChain chat model that supports tool calling:

```python
from langchain.chat_models import init_chat_model

llm = init_chat_model("claude-sonnet-5").bind_tools(tools)
msg = llm.invoke("Cast a Vedic chart for 12 Nov 1985, 06:45, Mumbai and tell me the Moon nakshatra.")
print(msg.tool_calls)
```

Or as a ReAct agent with LangGraph:

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(init_chat_model("claude-sonnet-5"), tools)
result = agent.invoke({"messages": [("user", "Are these two compatible? Arjun 1990-05-14 07:20 Pune; Meera 1992-11-03 22:45 Jaipur.")]})
print(result["messages"][-1].content)
```

The toolkit's methods also work without LangChain:

```python
kit = AsterwiseToolkit(api_key="aw_...")
kit.matchmaking("1990-05-14", "Pune, India", "1992-11-03", "Jaipur, India")
```

## Why the matchmaking tool reports vetoes separately

Rajju and Vedha between the two Moon nakshatras are stops in the classical method, not point deductions. A 30 out of 36 with Rajju present is not a good match, so the tool returns `classical_vetoes` alongside `total_score` and the tool description tells the model so. Background: [Rajju and Vedha as hard vetoes](https://asterwise.com/blog/rajju-vedha-hard-vetoes/).

## Accuracy

Every Asterwise position is computed with the Swiss Ephemeris and [checked against NASA JPL Horizons](https://asterwise.com/accuracy/): 80 positions from 1950 to 2050, median difference 0.046 arcseconds, raw data and script published.

## Test

```bash
pip install -e ".[test]" && pytest            # offline, mocks the SDK
ASTERWISE_API_KEY=aw_... python scripts/smoke.py   # one live call per tool
```

MIT licensed.
