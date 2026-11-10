"""Model Service Configuration."""

import os
from pathlib import Path
from pydantic import Field
from libs.common.config import BaseServiceSettings


class ModelSettings(BaseServiceSettings):
    service_name: str = "model-service"
    consumer_group: str = "model-service-group"
    consumer_name: str = "model-worker-1"
    artifacts_dir: str = Field(default="artifacts/models", env="MODEL_ARTIFACTS_DIR")
    poll_registry_seconds: int = 60


settings = ModelSettings()

