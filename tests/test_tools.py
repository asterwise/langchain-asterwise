import json
from types import SimpleNamespace

import pytest

from asterwise_langchain import AsterwiseToolkit


class _Resp:
    def __init__(self, data):
        self._d = {"success": True, "message": "success", "data": data}

    def to_dict(self):
        return self._d


@pytest.fixture
def kit(monkeypatch):
    kit = AsterwiseToolkit(api_key="aw_test")
    calls = {}

    def natal(req):
        calls["natal"] = req.to_dict()
        return _Resp({"planets": [{"name": "Sun", "sign": "Libra", "degree": 25.94, "nakshatra": "Vishakha", "house": 1, "extra": "drop me"}], "ascendant_sign": "Libra", "moon_sign": "Libra", "interpretation": "long text"})

    def match(req):
        calls["match"] = req.to_dict()
        return _Resp({"total_score": 16.5, "compatibility_level": "Average", "breakdown": {"Nadi": 0}, "classical_vetoes": {"has_veto": False}, "analysis": {"drop": 1}})

    def panch(req):
        calls["panchanga"] = req.to_dict()
        return _Resp({"tithi": {"name": "Krishna Ashtami"}, "nakshatra": {"name": "Rohini"}, "vara": "Friday", "muhurta_table": [1, 2, 3]})

    def western(req):
        calls["western"] = req.to_dict()
        return _Resp({"planets": [{"name": "Sun", "sign": "Scorpio", "degree_in_sign": 19.6, "house": 1, "longitude": 229.6}], "ascendant": {"sign": "Scorpio"}, "mc": {"sign": "Leo"}, "aspects": []})

    def numer(req):
        calls["numerology"] = req.to_dict()
        return _Resp({"life_path": 7})

    monkeypatch.setattr(kit.astrology, "natal_chart", natal)
    monkeypatch.setattr(kit.astrology, "matchmaking", match)
    monkeypatch.setattr(kit.astrology, "panchanga", panch)
    monkeypatch.setattr(kit.western, "western_natal_chart", western)
    monkeypatch.setattr(kit.numerology, "numerology_profile", numer)
    kit._calls = calls
    return kit


def test_toolkit_exposes_five_named_tools(kit):
    tools = kit.get_tools()
    assert [t.name for t in tools] == ["asterwise_natal_chart", "asterwise_western_natal_chart", "asterwise_matchmaking", "asterwise_panchanga", "asterwise_numerology_profile"]
    for t in tools:
        assert t.args_schema is not None and t.description


def test_natal_tool_maps_args_and_slims_output(kit):
    tool = kit.get_tools()[0]
    out = json.loads(tool.invoke({"date": "1985-11-12", "time": "06:45", "location": "Mumbai, India"}))
    assert kit._calls["natal"]["date"] == "1985-11-12" and kit._calls["natal"]["location"] == "Mumbai, India"
    assert out["planets"][0] == {"name": "Sun", "sign": "Libra", "degree": 25.94, "nakshatra": "Vishakha", "house": 1}
    assert "interpretation" not in out and out["moon_sign"] == "Libra"


def test_matchmaking_tool_keeps_vetoes_and_drops_analysis(kit):
    tool = kit.get_tools()[2]
    out = json.loads(tool.invoke({"person1_date": "1990-05-14", "person1_location": "Pune, India", "person2_date": "1992-11-03", "person2_location": "Jaipur, India"}))
    sent = kit._calls["match"]
    assert sent["person1"]["date"] == "1990-05-14" and sent["person2"]["location"] == "Jaipur, India"
    assert out["total_score"] == 16.5 and out["classical_vetoes"] == {"has_veto": False} and "analysis" not in out


def test_panchanga_and_western_slim(kit):
    tools = {t.name: t for t in kit.get_tools()}
    p = json.loads(tools["asterwise_panchanga"].invoke({"date": "2026-09-04", "location": "Delhi, India"}))
    assert p["nakshatra"] == {"name": "Rohini"} and "muhurta_table" not in p
    w = json.loads(tools["asterwise_western_natal_chart"].invoke({"date": "1985-11-12", "location": "Mumbai, India", "house_system": "koch"}))
    assert kit._calls["western"]["house_system"] == "koch"
    assert w["planets"][0]["degree_in_sign"] == 19.6 and "longitude" not in w["planets"][0] and "aspects" not in w


def test_full_payload_when_slim_disabled(monkeypatch):
    kit = AsterwiseToolkit(api_key="aw_test", slim=False)
    monkeypatch.setattr(kit.numerology, "numerology_profile", lambda req: _Resp({"life_path": 7, "extra": True}))
    assert kit.numerology_profile("Arjun", "1990-05-14") == {"life_path": 7, "extra": True}


def test_missing_key_is_rejected():
    with pytest.raises(ValueError):
        AsterwiseToolkit(api_key="")
