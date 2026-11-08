"""The SDK reports malformed gateway payloads through its public error type."""

import httpx
import pytest

from amberclaw.sdk.client import AmberClawClient, AsyncAmberClawClient
from amberclaw.sdk.exceptions import AmberClawAPIError

INVALID_JSON_BODIES = [b"[]", b"null", b'"scalar"', b"not-json"]


@pytest.mark.parametrize("body", INVALID_JSON_BODIES)
def test_sync_client_rejects_nonobject_health_response(body):
    with AmberClawClient() as client:
        client._client.close()
        client._client = httpx.Client(
            base_url=client.base_url,
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, content=body)
            ),
        )
        with pytest.raises(AmberClawAPIError, match="JSON object"):
            client.health()


@pytest.mark.parametrize("body", INVALID_JSON_BODIES)
@pytest.mark.asyncio
async def test_async_client_rejects_nonobject_health_response(body):
    async with AsyncAmberClawClient() as client:
        await client._client.aclose()
        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, content=body)
            ),
        )
        with pytest.raises(AmberClawAPIError, match="JSON object"):
            await client.health()
