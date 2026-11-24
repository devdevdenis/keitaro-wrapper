"""In-memory заглушка Keitaro для тестов (реализует протокол KeitaroAPI)."""

import copy
from datetime import UTC, datetime
from itertools import count

from app.keitaro.client import JSON
from app.keitaro.exceptions import KeitaroAPIError


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class FakeKeitaroClient:
    def __init__(self) -> None:
        self.domains: list[JSON] = [
            {"id": 1, "name": "track.example.com", "state": "active"},
            {"id": 2, "name": "go.example.net", "state": "active"},
        ]
        self.groups: list[JSON] = [
            {"id": 1, "name": "Tests", "type": "campaigns", "position": 1},
            {"id": 2, "name": "Nutra", "type": "campaigns", "position": 2},
        ]
        self.traffic_sources: list[JSON] = [
            {"id": 1, "name": "Facebook", "state": "active"},
            {"id": 2, "name": "Google Ads", "state": "active"},
            {"id": 3, "name": "TikTok", "state": "active"},
        ]
        self.offers: list[JSON] = [
            {"id": 101, "name": "Nutra Slim — DE", "state": "active", "country": ["DE"]},
            {"id": 102, "name": "Crypto Pro — GB", "state": "active", "country": ["GB"]},
            {"id": 103, "name": "Casino Royal — BR", "state": "active", "country": ["BR"]},
            {"id": 104, "name": "Dating Hot — US", "state": "active", "country": ["US"]},
        ]
        self.campaigns: dict[int, JSON] = {}
        self.streams: dict[int, JSON] = {}
        self._campaign_ids = count(1)
        self._stream_ids = count(1)
        self.fail_on_stream_create = False  # для тестов отката

    async def aclose(self) -> None:
        return None

    # --- справочники -------------------------------------------------------

    async def list_domains(self) -> list[JSON]:
        return copy.deepcopy(self.domains)

    async def list_groups(self, group_type: str = "campaigns") -> list[JSON]:
        return [copy.deepcopy(g) for g in self.groups if g["type"] == group_type]

    async def list_traffic_sources(self) -> list[JSON]:
        return copy.deepcopy(self.traffic_sources)

    async def list_offers(self) -> list[JSON]:
        return copy.deepcopy(self.offers)

    async def get_offer(self, offer_id: int) -> JSON:
        for offer in self.offers:
            if offer["id"] == offer_id:
                return copy.deepcopy(offer)
        raise KeitaroAPIError("Offer not found", status_code=404)

    # --- кампании ----------------------------------------------------------

    async def list_campaigns(self) -> list[JSON]:
        return [copy.deepcopy(c) for c in self.campaigns.values() if c["state"] != "deleted"]

    async def get_campaign(self, campaign_id: int) -> JSON:
        return copy.deepcopy(self._campaign(campaign_id))

    async def create_campaign(self, payload: JSON) -> JSON:
        missing = [f for f in ("alias", "name") if not payload.get(f)]
        if missing:
            raise KeitaroAPIError(
                "; ".join(f"{f}: required" for f in missing),
                status_code=406,
                details={f: ["required"] for f in missing},
            )
        campaign_id = next(self._campaign_ids)
        now = _now()
        campaign = {
            "id": campaign_id,
            "type": "position",
            "state": "active",
            "position": campaign_id,
            "created_at": now,
            "updated_at": now,
            **payload,
        }
        self.campaigns[campaign_id] = campaign
        return copy.deepcopy(campaign)

    async def update_campaign(self, campaign_id: int, payload: JSON) -> JSON:
        campaign = self._campaign(campaign_id)
        campaign.update(copy.deepcopy(payload))
        return copy.deepcopy(campaign)

    async def delete_campaign(self, campaign_id: int) -> JSON:
        campaign = self._campaign(campaign_id)
        campaign["state"] = "deleted"
        return copy.deepcopy(campaign)

    # --- потоки ------------------------------------------------------------

    async def list_streams(self, campaign_id: int) -> list[JSON]:
        self._campaign(campaign_id)
        streams = [
            s
            for s in self.streams.values()
            if s["campaign_id"] == campaign_id and s.get("state") != "deleted"
        ]
        return copy.deepcopy(sorted(streams, key=lambda s: s.get("position", 0)))

    async def get_stream(self, stream_id: int) -> JSON:
        return copy.deepcopy(self._stream(stream_id))

    async def create_stream(self, payload: JSON) -> JSON:
        if self.fail_on_stream_create:
            raise KeitaroAPIError("Stream creation failed (fake)", status_code=500)
        self._campaign(payload["campaign_id"])
        stream_id = next(self._stream_ids)
        stream = {
            "id": stream_id,
            "weight": 100,
            "collect_clicks": False,
            "filter_or": False,
            "filters": [],
            "landings": [],
            "offers": [],
            **copy.deepcopy(payload),
        }
        stream["filters"] = [
            {"id": i, "stream_id": stream_id, **f} for i, f in enumerate(stream["filters"], 1)
        ]
        stream["offers"] = self._materialize_offers(stream_id, stream["offers"])
        self.streams[stream_id] = stream
        return copy.deepcopy(stream)

    async def update_stream(self, stream_id: int, payload: JSON) -> JSON:
        stream = self._stream(stream_id)
        data = copy.deepcopy(payload)
        if "offers" in data:
            data["offers"] = self._materialize_offers(stream_id, data["offers"])
        if "filters" in data:
            data["filters"] = [
                {"id": i, "stream_id": stream_id, **f} for i, f in enumerate(data["filters"], 1)
            ]
        stream.update(data)
        return copy.deepcopy(stream)

    async def delete_stream(self, stream_id: int) -> JSON:
        self._stream(stream_id)["state"] = "deleted"
        return {"success": True}

    # --- helpers -----------------------------------------------------------

    def _campaign(self, campaign_id: int) -> JSON:
        campaign = self.campaigns.get(campaign_id)
        if campaign is None:
            raise KeitaroAPIError("Campaign not found", status_code=404)
        return campaign

    def _stream(self, stream_id: int) -> JSON:
        stream = self.streams.get(stream_id)
        if stream is None:
            raise KeitaroAPIError("Stream not found", status_code=404)
        return stream

    @staticmethod
    def _materialize_offers(stream_id: int, offers: list[JSON]) -> list[JSON]:
        return [
            {"id": i, "stream_id": stream_id, "state": "active", **o}
            for i, o in enumerate(offers, 1)
        ]
