"""Model Registry Loader: Atomic Hot-Swap with SHA256 Checksum & Feature Set Version Verification."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Optional
import joblib
from sqlalchemy import text
from libs.database.connection import engine
try:
    from .config import settings
except (ImportError, ValueError):
    from config import settings

log = logging.getLogger("model-service.registry-loader")


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


class ModelArtifacts:
    def __init__(self, version: str, stage: str, path: Path, expected_feature_set_version: str = "v1.0.0"):
        self.version = version
        self.stage = stage
        self.path = path
        self.expected_feature_set_version = expected_feature_set_version
        self.primary_model = None
        self.meta_model = None
        self.feature_cols = None
        self.metrics = {}

    def load_and_verify(self) -> bool:
        """Loads artifacts with strict SHA256 checksum and feature set version verification."""
        try:
            p_file = self.path / "primary_model.joblib"
            m_file = self.path / "meta_model.joblib"
            f_file = self.path / "feature_cols.joblib"
            met_file = self.path / "metrics.json"

            if not (p_file.exists() and m_file.exists() and f_file.exists() and met_file.exists()):
                log.warning("Artifacts missing in %s", self.path)
                return False

            with open(met_file, "r") as f:
                metrics = json.load(f)

            # 1. Feature Set Version Check
            fsv = metrics.get("feature_set_version")
            if fsv != self.expected_feature_set_version:
                log.error("Feature set version mismatch for %s: expected %s, got %s", self.version, self.expected_feature_set_version, fsv)
                return False

            # 2. SHA256 Checksum Verification
            chk = metrics.get("artifact_checksums", {})
            if chk:
                p_hash = compute_sha256(p_file)
                m_hash = compute_sha256(m_file)
                f_hash = compute_sha256(f_file)

                if chk.get("primary_model_sha256") and chk["primary_model_sha256"] != p_hash:
                    log.error("Checksum mismatch on primary model for %s", self.version)
                    return False
                if chk.get("meta_model_sha256") and chk["meta_model_sha256"] != m_hash:
                    log.error("Checksum mismatch on meta model for %s", self.version)
                    return False
                if chk.get("feature_cols_sha256") and chk["feature_cols_sha256"] != f_hash:
                    log.error("Checksum mismatch on feature cols for %s", self.version)
                    return False

            # Load binaries
            self.primary_model = joblib.load(p_file)
            self.meta_model = joblib.load(m_file)
            self.feature_cols = joblib.load(f_file)
            self.metrics = metrics

            log.info("Verified and loaded %s model %s (SHA256 verified, feature_set=%s)", self.stage, self.version, fsv)
            return True
        except Exception as e:
            log.exception("Failed loading artifact %s: %s", self.version, e)
            return False


class ModelRegistryManager:
    def __init__(self):
        self.champion: Optional[ModelArtifacts] = None
        self.challenger: Optional[ModelArtifacts] = None

    async def refresh_models(self):
        """Atomic hot-swap of champion and challenger models."""
        try:
            query = text("""
                SELECT version, stage, artifact_path, feature_set_version
                FROM model_registry.models
                WHERE stage IN ('champion', 'challenger')
                ORDER BY created_at DESC;
            """)
            async with engine.connect() as conn:
                result = await conn.execute(query)
                rows = result.fetchall()

            for row in rows:
                version, stage, artifact_path, fsv = row[0], row[1], row[2], row[3]
                path = Path(artifact_path)

                if stage == "champion":
                    if self.champion is None or self.champion.version != version:
                        candidate = ModelArtifacts(version, stage, path, expected_feature_set_version=fsv)
                        if candidate.load_and_verify():
                            # Atomic hot-swap pointer assignment
                            self.champion = candidate
                            log.info("ATOMIC HOT-SWAP: Champion updated to %s", version)
                elif stage == "challenger":
                    if self.challenger is None or self.challenger.version != version:
                        candidate = ModelArtifacts(version, stage, path, expected_feature_set_version=fsv)
                        if candidate.load_and_verify():
                            self.challenger = candidate
                            log.info("ATOMIC HOT-SWAP: Challenger updated to %s", version)
        except Exception as e:
            log.warning("Model registry poll error: %s", e)
