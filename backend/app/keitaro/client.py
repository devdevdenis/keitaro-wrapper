"""HTTP-клиент для Keitaro Admin API v1.

Документация: https://admin-api.docs.keitaro.io/ (OpenAPI: /openapi.json).
Авторизация — заголовок `Api-Key`, базовый путь — `/admin_api/v1`.
"""

from typing import Any, Protocol

import httpx

from app.keitaro.exceptions import KeitaroAPIError, KeitaroUnavailable

JSON = dict[str, Any]


class KeitaroAPI(Protocol):
    """Интерфейс, который реализуют настоящий клиент и заглушка (FakeKeitaroClient)."""

    async def list_domains(self) -> list[JSON]: ...
    async def list_groups(self, group_type: str = "campaigns") -> list[JSON]: ...
    async def list_traffic_sources(self) -> list[JSON]: ...
    async def list_offers(self) -> list[JSON]: ...

    async def list_campaigns(self) -> list[JSON]: ...
    async def get_campaign(self, campaign_id: int) -> JSON: ...
    async def create_campaign(self, payload: JSON) -> JSON: ...
    async def delete_campaign(self, campaign_id: int) -> JSON: ...

    async def list_streams(self, campaign_id: int) -> list[JSON]: ...
    async def get_stream(self, stream_id: int) -> JSON: ...
    async def create_stream(self, payload: JSON) -> JSON: ...
    async def update_stream(self, stream_id: int, payload: JSON) -> JSON: ...

    async def aclose(self) -> None: ...


class KeitaroClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._http = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/admin_api/v1",
            headers={"Api-Key": api_key, "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(
        self, method: str, path: str, *, params: JSON | None = None, json: JSON | None = None
    ) -> Any:
        try:
            response = await self._http.request(method, path, params=params, json=json)
        except httpx.HTTPError as exc:
            raise KeitaroUnavailable(f"Keitaro недоступен: {exc}") from exc

        if response.is_error:
            raise _to_api_error(response)
        if not response.content:
            return None
        return response.json()

    # --- справочники -------------------------------------------------------

    async def list_domains(self) -> list[JSON]:
        return await self._request("GET", "/domains")

    async def list_groups(self, group_type: str = "campaigns") -> list[JSON]:
        return await self._request("GET", "/groups", params={"type": group_type})

    async def list_traffic_sources(self) -> list[JSON]:
        return await self._request("GET", "/traffic_sources")

    async def list_offers(self) -> list[JSON]:
        return await self._request("GET", "/offers")

    # --- кампании ----------------------------------------------------------

    async def list_campaigns(self) -> list[JSON]:
        return await self._request("GET", "/campaigns")

    async def get_campaign(self, campaign_id: int) -> JSON:
        return await self._request("GET", f"/campaigns/{campaign_id}")

    async def create_campaign(self, payload: JSON) -> JSON:
        return await self._request("POST", "/campaigns", json=payload)

    async def delete_campaign(self, campaign_id: int) -> JSON:
        """Перемещает кампанию в архив."""
        return await self._request("DELETE", f"/campaigns/{campaign_id}")

    # --- потоки ------------------------------------------------------------

    async def list_streams(self, campaign_id: int) -> list[JSON]:
        return await self._request("GET", f"/campaigns/{campaign_id}/streams")

    async def get_stream(self, stream_id: int) -> JSON:
        return await self._request("GET", f"/streams/{stream_id}")

    async def create_stream(self, payload: JSON) -> JSON:
        return await self._request("POST", "/streams", json=payload)

    async def update_stream(self, stream_id: int, payload: JSON) -> JSON:
        return await self._request("PUT", f"/streams/{stream_id}", json=payload)


def _to_api_error(response: httpx.Response) -> KeitaroAPIError:
    """Keitaro отдаёт `{"error": "..."}`, а на 406 — словарь `{поле: [ошибки]}`."""
    details: Any = None
    message = f"Keitaro ответил {response.status_code}"
    try:
        body = response.json()
    except ValueError:
        body = response.text or None

    if isinstance(body, dict) and isinstance(body.get("error"), str):
        message = body["error"]
    elif isinstance(body, dict):
        details = body
        message = (
            "; ".join(
                f"{field}: {', '.join(map(str, errs)) if isinstance(errs, list) else errs}"
                for field, errs in body.items()
            )
            or message
        )
    elif isinstance(body, str):
        message = f"{message}: {body[:200]}"

    return KeitaroAPIError(message, status_code=response.status_code, details=details)
