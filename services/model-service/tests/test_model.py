"""Unit & integration tests for model-service."""

from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

try:
    from registry_loader import ModelArtifacts, ModelRegistryManager
    from inference import run_inference
    from consumer import ModelConsumer
    from main import app
except ImportError:
    from services.model_service.registry_loader import ModelArtifacts, ModelRegistryManager
    from services.model_service.inference import run_inference
    from services.model_service.consumer import ModelConsumer
    from services.model_service.main import app


def test_inference_execution():
    artifact = ModelArtifacts("LGBM-TEST", "champion", Path("/tmp"))
    
    # Mock primary model predict_proba
    mock_primary = MagicMock()
    mock_primary.predict_proba.return_value = np.array([[0.35, 0.65]])
    
    # Mock meta model predict_proba
    mock_meta = MagicMock()
    mock_meta.predict_proba.return_value = np.array([[0.20, 0.80]])

    artifact.primary_model = mock_primary
    artifact.meta_model = mock_meta
    artifact.feature_cols = ["rsi_14", "atr_14", "adx_14"]

    features = {"rsi_14": 55.0, "atr_14": 120.0, "adx_14": 28.0}
    res = run_inference(artifact, features)

    assert res is not None
    assert res["direction"] == "long"
    assert res["calibrated_probability"] == 0.65
    assert res["meta_confidence"] == 0.80
    assert res["model_version"] == "LGBM-TEST"


@pytest.mark.asyncio
async def test_consumer_champion_and_shadow_challenger():
    mock_stream_mgr = AsyncMock()
    reg_mgr = ModelRegistryManager()

    # Create mock champion
    champ = ModelArtifacts("LGBM-CHAMPION", "champion", Path("/tmp"))
    champ.primary_model = MagicMock()
    champ.primary_model.predict_proba.return_value = np.array([[0.30, 0.70]])
    champ.meta_model = MagicMock()
    champ.meta_model.predict_proba.return_value = np.array([[0.25, 0.75]])
    champ.feature_cols = ["rsi_14"]
    reg_mgr.champion = champ

    # Create mock challenger
    chal = ModelArtifacts("LGBM-CHALLENGER", "challenger", Path("/tmp"))
    chal.primary_model = MagicMock()
    chal.primary_model.predict_proba.return_value = np.array([[0.60, 0.40]])
    chal.meta_model = MagicMock()
    chal.meta_model.predict_proba.return_value = np.array([[0.30, 0.70]])
    chal.feature_cols = ["rsi_14"]
    reg_mgr.challenger = chal

    consumer = ModelConsumer(stream_mgr=mock_stream_mgr, registry_mgr=reg_mgr)

    event_payload = {
        "event_id": "22222222-2222-2222-2222-222222222222",
        "event_type": "features.ready",
        "event_version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "idempotency_key": "BTCUSDT:15m:1700000000000",
        "producer": "feature-service",
        "payload": {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "bar_timestamp": datetime.now(timezone.utc).isoformat(),
            "feature_set_version": "v1.0.0",
            "features": {"rsi_14": 48.0},
            "close_price": 50100.0,
        }
    }

    await consumer.handle_features_ready(event_payload)

    # Verifies both champion and shadow challenger published predictions
    assert mock_stream_mgr.publish.call_count == 2
    calls = mock_stream_mgr.publish.call_args_list

    # First call: Champion (is_shadow = False)
    champ_stream, champ_event = calls[0][0]
    assert champ_stream == "prediction.ready"
    assert champ_event.payload.is_shadow is False
    assert champ_event.payload.model_version == "LGBM-CHAMPION"
    assert champ_event.payload.direction == "long"

    # Second call: Challenger (is_shadow = True)
    chal_stream, chal_event = calls[1][0]
    assert chal_stream == "prediction.ready"
    assert chal_event.payload.is_shadow is True  # Shadow mode verified!
    assert chal_event.payload.model_version == "LGBM-CHALLENGER"
    assert chal_event.payload.direction == "short"


@pytest.mark.asyncio
async def test_model_service_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "model-service"
        assert data["status"] == "healthy"
