import pytest
from conftest import fixture

pytestmark = pytest.mark.anyio

TOOLS = {
    "rd_provinces",
    "rd_bulletin",
    "rd_closures",
    "rd_restrictions",
    "rd_workshops",
    "rd_weather",
    "rd_main_routes",
    "rd_traffic_map",
}


async def test_all_tools_are_read_only_and_described(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True, t.name
        assert t.title and t.description.splitlines()[0].endswith("."), t.name


async def test_provinces_and_name_filter(client, api):
    api["/provinces"] = fixture("provinces.json")
    api["/api/news/traffic-restriction/show"] = fixture("closures.json")
    r = (await client.call_tool("rd_provinces", {})).structured_content
    assert r[0]["id"] == 1 and isinstance(r[0]["lat"], float)
    # Arabic yeh/kaf and ZWNJ-free name still resolve; province id goes upstream
    name = fixture("provinces.json")["data"]["provinces"][1]["name_fa"]
    await client.call_tool("rd_closures", {"province": name})
    q = dict(api.calls[-1].url.params)
    assert q["province_id"] == "2" and q["per_page"] == "20"


async def test_unknown_province_is_an_error(client, api):
    api["/provinces"] = fixture("provinces.json")
    r = await client.call_tool("rd_closures", {"province": "ناکجاآباد"})
    assert r.is_error


async def test_closures_shape(client, api):
    api["/api/news/traffic-restriction/show"] = fixture("closures.json")
    r = (await client.call_tool("rd_closures", {})).structured_content
    assert r["total"] and r["items"][0]["axis"] and isinstance(r["items"][0]["lat"], float)
    assert r["items"][0]["cause"]


async def test_restrictions_workshops_weather_routes(client, api):
    api["/api/news/limitations/show"] = fixture("restrictions.json")
    api["/api/news/road_workshops/show"] = fixture("workshops.json")
    api["/news/weather/show"] = fixture("weather.json")
    api["/api/corridors/v2/show"] = fixture("main_routes.json")
    assert (await client.call_tool("rd_restrictions", {})).structured_content["items"][0]["vehicles"]
    w = (await client.call_tool("rd_workshops", {"limit": 5, "page": 2})).structured_content
    assert w["items"][0]["work"] and w["page"] == 2
    assert dict(api.calls[-1].url.params)["per_page"] == "5"
    assert (await client.call_tool("rd_weather", {})).structured_content[0]["hazard"]
    assert (await client.call_tool("rd_main_routes", {})).structured_content[0]["from"]


async def test_bulletin_strips_html(client, api):
    api["/news/roads/show"] = fixture("bulletin.json")
    r = (await client.call_tool("rd_bulletin", {})).structured_content
    assert r["bulletins"] and "<" not in r["bulletins"][0]["text"] and "&nbsp;" not in r["bulletins"][0]["text"]


async def test_traffic_map(client, api):
    api["/trafficimage"] = {"status": 1, "data": "https://api.141.ir/storage/Traffic/Tehran.jpeg?q=1"}
    r = (await client.call_tool("rd_traffic_map", {"province": 8})).structured_content
    assert r == {"province_id": 8, "image": "https://api.141.ir/storage/Traffic/Tehran.jpeg?q=1"}
    assert dict(api.calls[-1].url.params)["id"] == "8"
