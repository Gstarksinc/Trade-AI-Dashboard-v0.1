"""Model Inference Engine: LightGBM + Meta-Classifier."""

import logging
from typing import Dict, Optional
import numpy as np
import pandas as pd
try:
    from .registry_loader import ModelArtifacts
except (ImportError, ValueError):
    from registry_loader import ModelArtifacts

log = logging.getLogger("model-service.inference")


def run_inference(artifact: ModelArtifacts, features: Dict[str, float]) -> Optional[dict]:
    """Runs primary and meta model inference on feature dictionary."""
    if not (artifact and artifact.primary_model and artifact.feature_cols):
        return None

    try:
        # Construct single-row DataFrame aligned with training feature columns
        df_row = pd.DataFrame([features])
        missing_cols = [c for c in artifact.feature_cols if c not in df_row.columns]
        for c in missing_cols:
            df_row[c] = 0.0

        X = df_row[artifact.feature_cols].replace([np.inf, -np.inf], 0.0).fillna(0.0)

        # 1. Primary Model Prediction
        # CalibratedClassifierCV returns calibrated probabilities directly
        probs = artifact.primary_model.predict_proba(X)[0]
        prob_up = float(probs[1]) if len(probs) > 1 else float(probs[0])

        direction = "long" if prob_up >= 0.50 else "short"
        calibrated_prob = prob_up if direction == "long" else (1.0 - prob_up)
        raw_prob = calibrated_prob  # Since model is calibrated classifier

        # 2. Meta-Classifier Prediction
        X_meta = X.copy()
        X_meta["primary_prob"] = prob_up
        X_meta["primary_conf"] = abs(prob_up - 0.5)

        meta_prob = 0.60
        if artifact.meta_model:
            m_probs = artifact.meta_model.predict_proba(X_meta)[0]
            meta_prob = float(m_probs[1]) if len(m_probs) > 1 else float(m_probs[0])

        return {
            "direction": direction,
            "raw_probability": round(raw_prob, 4),
            "calibrated_probability": round(calibrated_prob, 4),
            "meta_confidence": round(meta_prob, 4),
            "model_version": artifact.version,
            "stage": artifact.stage,
        }
    except Exception as e:
        log.exception("Inference execution failed on model %s: %s", artifact.version, e)
        return None

