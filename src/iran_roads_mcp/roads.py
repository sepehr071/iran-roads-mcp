"""Road tools: bulletins, closures, police limits, road works, weather warnings, main routes, traffic maps."""

from __future__ import annotations

import html
import re
from typing import Annotated, Any

from pydantic import Field

from .http import API, ApiError, fetch
from .registry import tool

Province = Annotated[
    str | int | None,
    Field(description="Province id or Persian name (e.g. 8 or 'تهران'); see rd_provinces. Omit for the whole country"),
]
Limit = Annotated[int, Field(ge=1, le=50, description="Items per page")]
Page = Annotated[int, Field(ge=1, description="Page number, 1 = newest")]


def _norm(s: str) -> str:
    """Fold Arabic letters and ZWNJ so 'كرمان' matches 'کرمان'."""
    return s.replace("ك", "ک").replace("ي", "ی").replace("‌", " ").strip()


def _text(s: str | None) -> str | None:
    """HTML or plain site text to plain lines."""
    if not s:
        return None
    s = re.sub(r"</p>|<br\s*/?>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\r", "").replace("\xa0", " ")
    return "\n".join(x.strip() for x in s.split("\n") if x.strip())


async def _provinces() -> list[dict[str, Any]]:
    return (await fetch(f"{API}/provinces"))["data"]["provinces"]


async def _pid(province: str | int | None) -> int | None:
    if province is None or province == "":
        return None
    if isinstance(province, int) or str(province).strip().isdigit():
        return int(province)
    want = _norm(str(province))
    rows = await _provinces()
    hits = [p for p in rows if _norm(p["name_fa"]) == want] or [p for p in rows if want in _norm(p["name_fa"])]
    if len(hits) != 1:
        raise ApiError(f"Province '{province}' not found or ambiguous. Use an id from rd_provinces.")
    return hits[0]["id"]


def _paged(r: dict[str, Any], rows: list[dict[str, Any]], page: int) -> dict[str, Any]:
    return {"total": r.get("total"), "page": page, "pages": r.get("last_page"), "items": rows}


async def _list(path: str, province, limit: int, page: int) -> dict[str, Any]:
    q: dict[str, Any] = {"page": page, "per_page": limit}
    if (pid := await _pid(province)) is not None:
        q["province_id"] = pid
    return await fetch(f"{API}/api/news/{path}", q)


@tool("Provinces")
async def rd_provinces() -> list[dict[str, Any]]:
    """List the 31 provinces with the ids the other tools accept (and the province centre point)."""
    return [
        {
            "id": p["id"],
            "name": p["name_fa"],
            "slug": p["name_en"],
            "lat": float(p["center_lat"]),
            "lon": float(p["center_lon"]),
        }
        for p in await _provinces()
    ]


@tool("Road status bulletin")
async def rd_bulletin(province: Province = None) -> dict[str, Any]:
    """Latest official road weather and traffic status bulletin (northern axes, other axes) of the Road Maintenance Organization."""
    pid = await _pid(province)
    r = (await fetch(f"{API}/news/roads/show", {"province_id": pid} if pid else {}))["data"]
    return {
        "bulletins": [
            {
                "title": n["category_fa"],
                "province": n["province_fa"],
                "updated": n["updated_at"],
                "text": _text(n["body"]),
            }
            for n in r["road_news"]
        ],
        "note": None if r["road_news"] else "No bulletin for this province; national ones have no province filter.",
    }


@tool("Closed roads")
async def rd_closures(province: Province = None, limit: Limit = 20, page: Page = 1) -> dict[str, Any]:
    """List current road closures (blockades) with cause, direction, alternative route text and coordinates."""
    r = await _list("traffic-restriction/show", province, limit, page)
    rows = [
        {
            "id": x["id"],
            "axis": x["axis_name"],
            "province": x["province_fa"],
            "direction": x["direction_fa"],
            "cause": x["blockade_cause_fa"],
            "since": x["start_date_time"],
            "until": x["end_date_time"],
            "lat": float(x["lat"]) if x["lat"] else None,
            "lon": float(x["lon"]) if x["lon"] else None,
            "text": _text(x["text"]),
        }
        for x in r["data"]
    ]
    return _paged(r, rows, page)


@tool("Traffic restrictions")
async def rd_restrictions(province: Province = None, limit: Limit = 20, page: Page = 1) -> dict[str, Any]:
    """List traffic restrictions announced by the traffic police (limited vehicle types or hours, road still open)."""
    r = await _list("limitations/show", province, limit, page)
    rows = [
        {
            "id": x["id"],
            "axis": x["axis_name"],
            "province": x["province_fa"],
            "direction": x["direction_fa"],
            "vehicles": x["type_fa"],
            "since": x["start_date_time"],
            "until": x["end_date_time"],
            "lat": float(x["lat"]) if x["lat"] else None,
            "lon": float(x["lon"]) if x["lon"] else None,
            "text": _text(x["text"]),
        }
        for x in r["data"]
    ]
    return _paged(r, rows, page)


@tool("Road works")
async def rd_workshops(province: Province = None, limit: Limit = 20, page: Page = 1) -> dict[str, Any]:
    """List road works (workshops) with work type, whether traffic can pass, period and alternative route."""
    r = await _list("road_workshops/show", province, limit, page)
    rows = [
        {
            "id": x["id"],
            "axis": x["axis_name"],
            "province": x["province_fa"],
            "work": x["operation_fa"],
            "passable": x["pass_status_fa"],
            "from": x["start_date_time"],
            "to": x["end_date_time"],
            "alternative": x["alternative_route"],
            "lat": float(x["lat"]) if x["lat"] else None,
            "lon": float(x["lon"]) if x["lon"] else None,
            "text": _text(x["text"]),
        }
        for x in r["data"]
    ]
    return _paged(r, rows, page)


@tool("Road weather warnings")
async def rd_weather() -> list[dict[str, Any]]:
    """Current weather warnings for roads: hazard, affected provinces by day, and validity dates."""
    rows = (await fetch(f"{API}/news/weather/show"))["data"]["weather_news"]
    return [
        {
            "title": w["description"],
            "hazard": _text(w["risk_type"]),
            "regions": _text(w["affected_region"]),
            "from": w["start_date"],
            "to": w["end_date"],
            "updated": w["updated_at"],
        }
        for w in rows
    ]


@tool("Main routes")
async def rd_main_routes() -> list[dict[str, Any]]:
    """List the 22 main intercity axes the 141 app tracks (Tehran-North, Tehran-Mashhad...) with endpoints."""
    rows = (await fetch(f"{API}/api/corridors/v2/show"))["data"]["corridors"]
    return [
        {
            "id": c["id"],
            "axis": c["axis_name"],
            "from": c["source_name"],
            "to": c["destination_name"],
            "guide": c["links"],
        }
        for c in rows
    ]


@tool("Province traffic map")
async def rd_traffic_map(province: Province) -> dict[str, Any]:
    """Get the URL of the province's traffic status map image (updated by 141; the image shows live congestion)."""
    pid = await _pid(province)
    if pid is None:
        raise ApiError("Give a province id or name (see rd_provinces).")
    r = await fetch(f"{API}/trafficimage", {"id": pid})
    return {"province_id": pid, "image": r.get("data")}
