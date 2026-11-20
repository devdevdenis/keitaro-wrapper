import httpx
import pytest

from app.keitaro import KeitaroAPIError, KeitaroClient, KeitaroUnavailable


def make_client(handler) -> KeitaroClient:
    return KeitaroClient(
        "https://tracker.test/", "secret-key", transport=httpx.MockTransport(handler)
    )


async def test_sends_api_key_and_base_path():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("Api-Key")
        return httpx.Response(200, json=[{"id": 1, "name": "Tests", "type": "campaigns"}])

    client = make_client(handler)
    groups = await client.list_groups()
    await client.aclose()

    assert seen["url"] == "https://tracker.test/admin_api/v1/groups?type=campaigns"
    assert seen["key"] == "secret-key"
    assert groups[0]["name"] == "Tests"


async def test_error_message_is_extracted():
    client = make_client(lambda r: httpx.Response(404, json={"error": "Not found"}))
    with pytest.raises(KeitaroAPIError) as exc:
        await client.get_campaign(1)
    assert exc.value.status_code == 404
    assert exc.value.message == "Not found"


async def test_validation_errors_are_extracted():
    client = make_client(lambda r: httpx.Response(406, json={"alias": ["Alias is taken"]}))
    with pytest.raises(KeitaroAPIError) as exc:
        await client.create_campaign({"name": "x", "alias": "y"})
    assert exc.value.details == {"alias": ["Alias is taken"]}
    assert "Alias is taken" in exc.value.message


async def test_network_error_is_wrapped():
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    client = make_client(handler)
    with pytest.raises(KeitaroUnavailable):
        await client.list_offers()
