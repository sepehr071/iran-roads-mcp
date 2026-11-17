import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_live_provinces_and_bulletin(client):
    p = (await client.call_tool("rd_provinces", {})).structured_content
    assert len(p) == 31
    b = (await client.call_tool("rd_bulletin", {})).structured_content
    assert b["bulletins"] and b["bulletins"][0]["text"]


async def test_live_lists(client):
    c = (await client.call_tool("rd_closures", {"limit": 3})).structured_content
    assert c["total"] is not None and len(c["items"]) <= 3
    w = (await client.call_tool("rd_workshops", {"province": "تهران", "limit": 3})).structured_content
    assert all(x["province"] == "تهران" for x in w["items"])
    assert (await client.call_tool("rd_restrictions", {})).structured_content["total"] is not None
    assert len((await client.call_tool("rd_main_routes", {})).structured_content) >= 20
    assert (await client.call_tool("rd_weather", {})).structured_content is not None


async def test_live_traffic_map(client):
    r = (await client.call_tool("rd_traffic_map", {"province": "تهران"})).structured_content
    assert r["image"].startswith("https://api.141.ir/storage/Traffic/")
