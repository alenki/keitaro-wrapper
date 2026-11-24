import pytest


@pytest.fixture
def static_dir(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    return tmp_path


async def test_root_serves_the_app_without_caching(make_client, static_dir):
    async with make_client(static_dir=str(static_dir)) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "<title>app</title>" in response.text
    assert response.headers["cache-control"] == "no-cache"


async def test_app_routes_fall_back_to_index_html(make_client, static_dir):
    async with make_client(static_dir=str(static_dir)) as client:
        response = await client.get("/campaigns/42")

    assert response.status_code == 200
    assert "<title>app</title>" in response.text


async def test_hashed_assets_are_cached_for_a_long_time(make_client, static_dir):
    async with make_client(static_dir=str(static_dir)) as client:
        response = await client.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.text == "console.log(1)"
    assert "immutable" in response.headers["cache-control"]


async def test_files_in_the_root_are_served(make_client, static_dir):
    async with make_client(static_dir=str(static_dir)) as client:
        response = await client.get("/favicon.svg")

    assert response.text == "<svg/>"


async def test_unknown_api_route_stays_a_json_404(make_client, static_dir):
    async with make_client(static_dir=str(static_dir)) as client:
        response = await client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_files_outside_the_static_dir_are_not_served(make_client, static_dir):
    (static_dir.parent / "secret.txt").write_text("secret", encoding="utf-8")

    async with make_client(static_dir=str(static_dir)) as client:
        response = await client.get("/..%2fsecret.txt")

    assert "secret" not in response.text


async def test_without_a_build_only_the_api_is_served(make_client, tmp_path):
    async with make_client(static_dir=str(tmp_path / "missing")) as client:
        response = await client.get("/")

    assert response.status_code == 404
