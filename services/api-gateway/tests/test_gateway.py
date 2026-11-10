import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_gateway_health():
    import importlib
    main_mod = importlib.import_module("services.api-gateway.main")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "api-gateway"
        assert data["status"] == "healthy"

