"""LangChain tools for the Asterwise astrology API.

    from asterwise_langchain import AsterwiseToolkit
    tools = AsterwiseToolkit(api_key="aw_...").get_tools()

Five StructuredTools, each a thin wrapper over the official ``asterwise`` SDK:
natal_chart, western_natal_chart, matchmaking, panchanga, numerology_profile.
By default outputs are slimmed to what a model needs to reason; pass
``slim=False`` to return the full API payload.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

import asterwise
from asterwise.api.astrology_api import AstrologyApi
from asterwise.api.numerology_api import NumerologyApi
from asterwise.api.western_astrology_api import WesternAstrologyApi

__all__ = ["AsterwiseToolkit", "__version__"]
__version__ = "0.1.0"

_AYANAMSA = "Sidereal ayanamsa: lahiri (default), raman, kp, or tropical."


class BirthArgs(BaseModel):
    """Birth data. Give a birthplace as text; the API geocodes it and resolves the time zone."""

    date: str = Field(description="Date of birth, YYYY-MM-DD.")
    time: Optional[str] = Field(default=None, description="Time of birth, HH:MM 24-hour. Omit if unknown; a sunrise chart is used.")
    location: str = Field(description="Birthplace, e.g. 'Mumbai, India'.")
    name: Optional[str] = Field(default=None, description="Person's name, optional.")
    ayanamsa: Optional[str] = Field(default=None, description=_AYANAMSA)


class WesternBirthArgs(BaseModel):
    date: str = Field(description="Date of birth, YYYY-MM-DD.")
    time: Optional[str] = Field(default=None, description="Time of birth, HH:MM 24-hour. Omit if unknown.")
    location: str = Field(description="Birthplace, e.g. 'Austin, Texas'.")
    name: Optional[str] = Field(default=None, description="Person's name, optional.")
    house_system: Optional[str] = Field(default=None, description="placidus (default), koch, equal, or whole_sign.")


class MatchArgs(BaseModel):
    """Two people. person1 is the groom and person2 the bride in the classical Ashtakoot method."""

    person1_date: str = Field(description="First person's date of birth, YYYY-MM-DD.")
    person1_location: str = Field(description="First person's birthplace.")
    person1_time: Optional[str] = Field(default=None, description="First person's time of birth, HH:MM, optional.")
    person1_name: Optional[str] = Field(default=None)
    person2_date: str = Field(description="Second person's date of birth, YYYY-MM-DD.")
    person2_location: str = Field(description="Second person's birthplace.")
    person2_time: Optional[str] = Field(default=None, description="Second person's time of birth, HH:MM, optional.")
    person2_name: Optional[str] = Field(default=None)


class PanchangaArgs(BaseModel):
    date: str = Field(description="Civil date, YYYY-MM-DD.")
    location: str = Field(description="Place, e.g. 'New Delhi, India'. Sunrise and the day's elements depend on it.")


class NumerologyArgs(BaseModel):
    name: str = Field(description="Full name as commonly written.")
    date: str = Field(description="Date of birth, YYYY-MM-DD.")


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _slim_natal(d: dict[str, Any]) -> dict[str, Any]:
    keep = {}
    planets = d.get("planets")
    if isinstance(planets, list):
        keep["planets"] = [
            {k: p.get(k) for k in ("name", "sign", "degree", "nakshatra", "pada", "house", "retrograde") if k in p}
            for p in planets
            if isinstance(p, dict)
        ]
    for k in ("ascendant", "ascendant_sign", "moon_sign", "moon_nakshatra", "ayanamsa_used", "ayanamsa_value", "birth_time_provided"):
        if k in d:
            keep[k] = d[k]
    return keep or d


def _slim_western(d: dict[str, Any]) -> dict[str, Any]:
    keep = {}
    planets = d.get("planets")
    if isinstance(planets, list):
        keep["planets"] = [
            {k: p.get(k) for k in ("name", "sign", "degree_in_sign", "house", "is_retrograde", "dignity") if k in p}
            for p in planets
            if isinstance(p, dict)
        ]
    for k in ("ascendant", "mc", "house_system", "birth_time_provided"):
        if k in d:
            keep[k] = d[k]
    return keep or d


def _slim_match(d: dict[str, Any]) -> dict[str, Any]:
    keep = {k: d[k] for k in ("total_score", "compatibility_level", "breakdown", "classical_vetoes", "doshas", "dosha_cancellations", "mangal_compatibility", "compatibility_narrative", "birth_time_provided") if k in d}
    return keep or d


def _slim_panchanga(d: dict[str, Any]) -> dict[str, Any]:
    keep = {k: d[k] for k in ("date", "vara", "tithi", "nakshatra", "yoga", "karana", "sunrise", "sunset", "moonrise", "moonset", "rahu_kaal", "location") if k in d}
    return keep or d


def _to_dict(result: Any) -> dict[str, Any]:
    """Unwrap the SDK's {success, message, data} envelope to the data dict."""
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    if isinstance(result, dict) and "data" in result and isinstance(result["data"], dict):
        return result["data"]
    return result


class AsterwiseToolkit:
    """Builds LangChain tools bound to one Asterwise API key.

    Args:
        api_key: an Asterwise API key (free tier at https://asterwise.com/dashboard).
        slim: when True (default) each tool returns only the fields a model needs;
            when False the full API payload is returned.
        host: API base URL, normally left as the default.
    """

    def __init__(self, api_key: str, *, slim: bool = True, host: str = "https://api.asterwise.com") -> None:
        if not api_key:
            raise ValueError("api_key is required; get one at https://asterwise.com/dashboard")
        self._config = asterwise.Configuration(host=host, access_token=api_key)
        self._client = asterwise.ApiClient(self._config)
        self.slim = slim
        self.astrology = AstrologyApi(self._client)
        self.western = WesternAstrologyApi(self._client)
        self.numerology = NumerologyApi(self._client)

    # ---- individual calls (plain functions so they are easy to test and reuse) ----

    def natal_chart(self, date: str, location: str, time: Optional[str] = None, name: Optional[str] = None, ayanamsa: Optional[str] = None) -> dict[str, Any]:
        req = asterwise.NatalRequest(**_drop_none({"date": date, "time": time, "location": location, "name": name, "ayanamsa": ayanamsa}))
        d = _to_dict(self.astrology.natal_chart(req))
        return _slim_natal(d) if self.slim else d

    def western_natal_chart(self, date: str, location: str, time: Optional[str] = None, name: Optional[str] = None, house_system: Optional[str] = None) -> dict[str, Any]:
        req = asterwise.WesternNatalRequest(**_drop_none({"date": date, "time": time, "location": location, "name": name, "house_system": house_system}))
        d = _to_dict(self.western.western_natal_chart(req))
        return _slim_western(d) if self.slim else d

    def matchmaking(self, person1_date: str, person1_location: str, person2_date: str, person2_location: str, person1_time: Optional[str] = None, person1_name: Optional[str] = None, person2_time: Optional[str] = None, person2_name: Optional[str] = None) -> dict[str, Any]:
        p1 = asterwise.BirthInput(**_drop_none({"date": person1_date, "time": person1_time, "location": person1_location, "name": person1_name}))
        p2 = asterwise.BirthInput(**_drop_none({"date": person2_date, "time": person2_time, "location": person2_location, "name": person2_name}))
        d = _to_dict(self.astrology.matchmaking(asterwise.MatchmakingRequest(person1=p1, person2=p2)))
        return _slim_match(d) if self.slim else d

    def panchanga(self, date: str, location: str) -> dict[str, Any]:
        d = _to_dict(self.astrology.panchanga(asterwise.PanchangaRequest(date=date, location=location)))
        return _slim_panchanga(d) if self.slim else d

    def numerology_profile(self, name: str, date: str) -> dict[str, Any]:
        return _to_dict(self.numerology.numerology_profile(asterwise.NumerologyRequest(name=name, date=date)))

    # ---- LangChain tools ----

    def get_tools(self) -> list[StructuredTool]:
        def wrap(fn: Callable[..., dict[str, Any]]) -> Callable[..., str]:
            def run(**kwargs: Any) -> str:
                return json.dumps(fn(**kwargs), ensure_ascii=False, default=str)
            return run

        return [
            StructuredTool.from_function(
                func=wrap(self.natal_chart), name="asterwise_natal_chart", args_schema=BirthArgs,
                description="Vedic (sidereal) natal chart: planets by sign, degree, nakshatra and house, plus the ascendant and Moon sign. Use for any Jyotish question about a person's birth chart.",
            ),
            StructuredTool.from_function(
                func=wrap(self.western_natal_chart), name="asterwise_western_natal_chart", args_schema=WesternBirthArgs,
                description="Western (tropical) natal chart: planets by sign and house, ascendant and midheaven, Placidus by default.",
            ),
            StructuredTool.from_function(
                func=wrap(self.matchmaking), name="asterwise_matchmaking", args_schema=MatchArgs,
                description="Vedic marriage compatibility (Ashtakoot Guna Milan out of 36) for two people, with Rajju and Vedha reported as separate classical vetoes, Mangal dosha comparison, and a narrative. A match with a veto is not a good match regardless of score.",
            ),
            StructuredTool.from_function(
                func=wrap(self.panchanga), name="asterwise_panchanga", args_schema=PanchangaArgs,
                description="Daily panchanga for a date and place: tithi, nakshatra, yoga, karana, vara, sunrise and sunset, Rahu kaal.",
            ),
            StructuredTool.from_function(
                func=wrap(self.numerology_profile), name="asterwise_numerology_profile", args_schema=NumerologyArgs,
                description="Pythagorean numerology profile from a name and date of birth: life path, expression, soul urge, personality and related numbers.",
            ),
        ]
