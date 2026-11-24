import json
import logging

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.log import JsonFormatter, request_id_var
from tests.helpers import make_settings


async def test_health_reports_ok_when_database_is_up(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_reports_503_when_database_is_down(make_client):
    closed_port_url = "postgresql+asyncpg://wrapper:wrapper@127.0.0.1:1/x"
    async with make_client(database_url=closed_port_url) as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}


async def test_request_id_is_generated_for_every_response(client):
    response = await client.get("/health")

    request_id = response.headers["x-request-id"]
    assert len(request_id) == 32
    int(request_id, 16)


async def test_incoming_request_id_is_kept(client):
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["x-request-id"] == "abc-123"


async def test_unsafe_incoming_request_id_is_replaced(client):
    response = await client.get("/health", headers={"X-Request-ID": "x" * 200})

    assert len(response.headers["x-request-id"]) == 32


async def test_unknown_api_route_returns_json_error(client):
    response = await client.get("/api/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["x-request-id"]


async def test_every_request_is_logged_once(client, caplog):
    caplog.set_level(logging.INFO, logger="app.access")

    await client.get("/api/does-not-exist")

    [record] = [r for r in caplog.records if r.name == "app.access"]
    assert record.method == "GET"
    assert record.path == "/api/does-not-exist"
    assert record.status == 404
    assert record.duration_ms >= 0


def test_settings_reject_prefix_without_trailing_underscore():
    with pytest.raises(ValidationError, match="campaign_prefix"):
        make_settings(campaign_prefix="test_karaf")


def test_settings_require_api_key(monkeypatch):
    monkeypatch.delenv("KEITARO_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="keitaro_api_key"):
        Settings(_env_file=None, database_url="postgresql+asyncpg://u:p@localhost/db")


def test_settings_reject_an_empty_api_key():
    with pytest.raises(ValidationError, match="KEITARO_API_KEY"):
        make_settings(keitaro_api_key="  ")


def test_settings_reject_database_url_without_asyncpg_driver():
    with pytest.raises(ValidationError, match="database_url"):
        make_settings(database_url="postgresql://u:p@localhost/db")


def test_settings_strip_trailing_slash_from_keitaro_url():
    settings = make_settings(keitaro_url="https://kt.example.com/")

    assert settings.keitaro_url == "https://kt.example.com"


def test_api_key_is_not_shown_in_settings_repr():
    assert "test-key" not in repr(make_settings())


def test_json_log_line_has_request_id_and_extra_fields():
    token = request_id_var.set("req-1")
    try:
        record = logging.makeLogRecord(
            {
                "name": "app.test",
                "levelno": logging.INFO,
                "levelname": "INFO",
                "msg": "hello %s",
                "args": ("world",),
            }
        )
        record.campaign_id = 42
        line = JsonFormatter().format(record)
    finally:
        request_id_var.reset(token)

    data = json.loads(line)
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert data["logger"] == "app.test"
    assert data["request_id"] == "req-1"
    assert data["campaign_id"] == 42
