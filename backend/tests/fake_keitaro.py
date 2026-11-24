"""In-memory stand-in for the Keitaro emulator, served to the app through httpx.ASGITransport.

Status codes and error texts copy what the real emulator returned when probed:
401 {"error": "Unauthorized"}, 404 {"error": "Campaign not found"},
406 {"error": "offers: offer 1 does not exist"}; creates answer 200 with the full object.
"""

import copy
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

API_KEY = "test-key"

OFFERS = [
    {"id": 18001, "name": "18001 Detoxin [HAIR-CL] [vsl es -] CPAHUB v2", "country": ["CL"]},
    {
        "id": 18002,
        "name": "18002 Fungiclean [PARASITE-TH] [spin th -] OFFERIA v1",
        "country": ["TH"],
    },
    {"id": 18003, "name": "18003 Slimora [DIET-CO] [article es -] LEADFOX v1", "country": ["CO"]},
    {"id": 18004, "name": "18004 Hepatix [PROSTATE-DE] [quiz de -] ADNOVA v3", "country": ["DE"]},
    {"id": 18005, "name": "18005 Cardiolux [HAIR-CO] [quiz es -] CPAHUB v3", "country": ["CO"]},
    {"id": 18100, "name": "18100 Hairmax [HAIR-DE] [spin de -] LEADFOX v1", "country": ["DE"]},
]


@dataclass
class Call:
    method: str
    path: str
    body: Any = None


@dataclass
class Failure:
    method: str
    path: str
    status: int
    error: str
    skip: int
    times: int


@dataclass
class FakeKeitaro:
    offers: dict[int, dict] = field(
        default_factory=lambda: {o["id"]: {**o, "state": "active"} for o in OFFERS}
    )
    domains: list[dict] = field(default_factory=lambda: [{"id": 1813, "name": "kt-emulator.test"}])
    groups: list[dict] = field(default_factory=lambda: [{"id": 10332, "name": "FORTESTS"}])
    sources: list[dict] = field(default_factory=lambda: [{"id": 836, "name": "FORTESTS"}])
    campaigns: dict[int, dict] = field(default_factory=dict)
    streams: dict[int, dict] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    next_id: int = 100

    def __post_init__(self) -> None:
        self.app = self._build_app()

    # Helpers for tests

    def fail(
        self,
        method: str,
        path: str,
        *,
        status: int = 500,
        error: str = "boom",
        skip: int = 0,
        times: int = 1,
    ) -> None:
        """Answer the matching request with an error, after letting `skip` of them through."""
        self.failures.append(Failure(method, path, status, error, skip, times))

    def requests(self, method: str | None = None, path: str | None = None) -> list[Call]:
        return [
            c
            for c in self.calls
            if (method is None or c.method == method) and (path is None or c.path == path)
        ]

    def add_campaign(self, name: str = "test_karaf_existing", **fields) -> dict:
        campaign = self._new_campaign({"name": name, **fields})
        self.campaigns[campaign["id"]] = campaign
        return campaign

    def add_stream(self, campaign_id: int, **fields) -> dict:
        stream = self._new_stream({"campaign_id": campaign_id, "name": "Stream", **fields})
        self.streams[stream["id"]] = stream
        return stream

    def add_campaign_with_streams(
        self, offers: list[tuple[int, int]], *, name: str = "test_karaf_campaign1"
    ) -> tuple[dict, dict, dict]:
        """A campaign shaped like the ones the creator makes: geo -> Google, then offers."""
        campaign = self.add_campaign(name, domain_id=1813, group_id=10332, traffic_source_id=836)
        geo = self.add_stream(
            campaign["id"],
            name="Geo AU",
            schema="redirect",
            action_payload="https://google.com",
            filters=[{"name": "country", "mode": "accept", "payload": ["AU"]}],
        )
        offers_stream = self.add_stream(
            campaign["id"],
            name="Offers",
            type="default",
            offers=[{"offer_id": offer_id, "share": share} for offer_id, share in offers],
        )
        return campaign, geo, offers_stream

    def set_stream_offers(self, stream_id: int, offers: list[tuple[int, int, str]]) -> None:
        """Change offers the way somebody would in the Keitaro admin."""
        self.streams[stream_id]["offers"] = [
            {"offer_id": offer_id, "share": share, "state": state}
            for offer_id, share, state in offers
        ]

    def stream_offers(self, stream_id: int) -> list[tuple[int, int, str]]:
        return [(o["offer_id"], o["share"], o["state"]) for o in self.streams[stream_id]["offers"]]

    # Fake objects

    def _id(self) -> int:
        self.next_id += 1
        return self.next_id

    def _new_campaign(self, payload: dict) -> dict:
        campaign_id = self._id()
        return {
            "id": campaign_id,
            "alias": f"alias{campaign_id}",
            "type": "position",
            "state": "active",
            "cost_type": "CPC",
            "cost_value": 0,
            "cost_currency": "USD",
            "cost_auto": False,
            "group_id": None,
            "traffic_source_id": None,
            "domain_id": None,
            "token": "secret-campaign-token",
            "updated_at": "2026-11-24 09:37:20",
            **payload,
        }

    def _new_stream(self, payload: dict) -> dict:
        siblings = [s for s in self.streams.values() if s["campaign_id"] == payload["campaign_id"]]
        offers = [
            {
                "offer_id": o["offer_id"],
                "share": o.get("share", 0),
                "state": o.get("state", "active"),
            }
            for o in payload.pop("offers", [])
        ]
        return {
            "id": self._id(),
            "type": "regular",
            "schema": "landings",
            "state": "active",
            "action_type": "http",
            "action_payload": None,
            "position": len(siblings) + 1,
            "filters": [],
            **payload,
            "offers": offers,
        }

    def _check_offers(self, offers: list[dict]) -> JSONResponse | None:
        for offer in offers:
            if offer["offer_id"] not in self.offers:
                return _error(406, f"offers: offer {offer['offer_id']} does not exist")
        return None

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        prefix = "/admin_api/v1"

        @app.middleware("http")
        async def record_and_fail(request: Request, call_next):
            if request.headers.get("Api-Key") != API_KEY:
                return _error(401, "Unauthorized")
            path = request.url.path.removeprefix(prefix)
            body = await request.json() if request.method in ("POST", "PUT") else None
            self.calls.append(Call(request.method, path, body))
            for failure in self.failures:
                if failure.method == request.method and failure.path == path and failure.times:
                    if failure.skip:
                        failure.skip -= 1
                        continue
                    failure.times -= 1
                    return _error(failure.status, failure.error)
            return await call_next(request)

        @app.get(prefix + "/offers")
        async def list_offers():
            return list(self.offers.values())

        @app.get(prefix + "/domains")
        async def list_domains():
            return self.domains

        @app.get(prefix + "/groups")
        async def list_groups(type: str = "campaigns"):
            return self.groups if type == "campaigns" else []

        @app.get(prefix + "/traffic_sources")
        async def list_sources():
            return self.sources

        @app.get(prefix + "/campaigns")
        async def list_campaigns():
            return sorted(self.campaigns.values(), key=lambda c: -c["id"])

        @app.post(prefix + "/campaigns")
        async def create_campaign(request: Request):
            campaign = self._new_campaign(await request.json())
            self.campaigns[campaign["id"]] = campaign
            return campaign

        @app.get(prefix + "/campaigns/{campaign_id}")
        async def get_campaign(campaign_id: int):
            campaign = self.campaigns.get(campaign_id)
            return campaign if campaign else _error(404, "Campaign not found")

        @app.delete(prefix + "/campaigns/{campaign_id}")
        async def delete_campaign(campaign_id: int):
            campaign = self.campaigns.pop(campaign_id, None)
            if campaign is None:
                return _error(404, "Campaign not found")
            for stream_id in [
                s["id"] for s in self.streams.values() if s["campaign_id"] == campaign_id
            ]:
                del self.streams[stream_id]
            return {**campaign, "state": "deleted"}

        @app.get(prefix + "/campaigns/{campaign_id}/streams")
        async def list_streams(campaign_id: int):
            if campaign_id not in self.campaigns:
                return _error(404, "Campaign not found")
            streams = [s for s in self.streams.values() if s["campaign_id"] == campaign_id]
            return sorted(streams, key=lambda s: s["position"])

        @app.post(prefix + "/streams")
        async def create_stream(request: Request):
            payload = await request.json()
            if payload.get("campaign_id") not in self.campaigns:
                return _error(404, "Campaign not found")
            if error := self._check_offers(payload.get("offers", [])):
                return error
            stream = self._new_stream(payload)
            self.streams[stream["id"]] = stream
            return stream

        @app.get(prefix + "/streams/{stream_id}")
        async def get_stream(stream_id: int):
            stream = self.streams.get(stream_id)
            return stream if stream else _error(404, "Stream not found")

        @app.put(prefix + "/streams/{stream_id}")
        async def update_stream(stream_id: int, request: Request):
            stream = self.streams.get(stream_id)
            if stream is None:
                return _error(404, "Stream not found")
            payload = await request.json()
            if "offers" in payload:
                if error := self._check_offers(payload["offers"]):
                    return error
                stream["offers"] = [
                    {"offer_id": o["offer_id"], "share": o["share"], "state": o["state"]}
                    for o in payload["offers"]
                ]
            return copy.deepcopy(stream)

        return app


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)
