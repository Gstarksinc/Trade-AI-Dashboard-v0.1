"""Training Service Main Application with Admin Auth and Batch Training Engine."""

import asyncio
from contextlib import asynccontextmanager
import logging
import os
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from libs.common.config import BaseServiceSettings
from libs.common.logging import setup_structured_logging
from libs.common.metrics import setup_metrics_endpoint
try:
    from .trainer import ModelTrainer
except (ImportError, ValueError):
    from trainer import ModelTrainer

log = setup_structured_logging("training-service")

security = HTTPBearer(auto_error=False)


class TrainingSettings(BaseServiceSettings):
    service_name: str = "training-service"
    admin_api_key: str = Field(default="admin_secret_key_123", env="ADMIN_API_KEY")


settings = TrainingSettings()
trainer = ModelTrainer()
training_in_progress = False


class TrainRequest(BaseModel):
    symbol: Optional[str] = "BTCUSDT"
    timeframe: Optional[str] = "15m"
    force_promote: Optional[bool] = False


def verify_admin_auth(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    auth: Optional[HTTPAuthorizationCredentials] = Security(security),
):
    token = None
    if x_admin_key:
        token = x_admin_key
    elif auth and auth.credentials:
        token = auth.credentials

    if not token or token != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing admin key")
    return token


async def run_training_job(symbol: str, timeframe: str, force_promote: bool = False):
    global training_in_progress
    training_in_progress = True
    try:
        log.info("Batch training job started for %s %s...", symbol, timeframe)
        candles, features = await trainer.load_training_data(symbol, timeframe, limit=3500)
        if len(candles) < 150:
            log.warning("Insufficient data for training: %d bars found", len(candles))
            return None

        result = trainer.run_training_pipeline(candles, features, symbol, timeframe)
        version = result["version"]
        metrics = result["metrics"]
        promotion_approved = result["promotion_approved"]

        champion = await trainer.get_current_champion()
        should_promote = False

        # Phase 3.1: NO auto-champion on cold start. Promotion gates must pass.
        if promotion_approved or force_promote:
            if champion is None:
                log.info("Candidate %s passed all promotion gates on cold start. Promoting to Champion!", version)
                should_promote = True
            else:
                champ_ev = champion.get("metrics", {}).get("holdout_evaluation", {}).get("net_ev_pct", 0.0)
                cand_ev = metrics.get("holdout_evaluation", {}).get("net_ev_pct", 0.0)
                if cand_ev > champ_ev:
                    log.info("Candidate %s passed gates and beats champion %s (EV: %.3f vs %.3f). Promoting!", version, champion["version"], cand_ev, champ_ev)
                    should_promote = True
                    await trainer.record_model(
                        version=champion["version"],
                        stage="retired",
                        algorithm=champion["algorithm"],
                        feature_set_version=champion["feature_set_version"],
                        metrics=champion["metrics"],
                        artifact_path=champion["artifact_path"],
                    )
        else:
            log.warning("Candidate %s FAILED promotion gates. Enrolling as Challenger (Shadow Mode).", version)

        stage = "champion" if should_promote else "challenger"
        await trainer.record_model(
            version=version,
            stage=stage,
            algorithm="LightGBM + CalibratedClassifierCV + RF Meta",
            feature_set_version="v1.0.0",
            metrics=metrics,
            artifact_path=result["artifact_path"],
        )
        await trainer.record_drift_report(version, result["drift_report"])
        log.info("Training job finished for %s. Registered with stage: %s", version, stage)
        return result

    except Exception as e:
        log.exception("Training job failed: %s", e)
        return None
    finally:
        training_in_progress = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting training-service...")
    yield
    log.info("Stopped training-service.")


app = FastAPI(title="training-service", lifespan=lifespan)
setup_metrics_endpoint(app)


@app.get("/health")
async def health():
    champion = await trainer.get_current_champion()
    return {
        "service": "training-service",
        "status": "healthy",
        "training_in_progress": training_in_progress,
        "current_champion": champion["version"] if champion else None,
    }


@app.post("/train")
async def trigger_training(
    req: TrainRequest,
    background_tasks: BackgroundTasks,
    auth: str = Security(verify_admin_auth),
):
    global training_in_progress
    if training_in_progress:
        raise HTTPException(status_code=409, detail="A training run is already in progress.")

    background_tasks.add_task(run_training_job, req.symbol, req.timeframe, req.force_promote)
    return {
        "status": "training_scheduled",
        "symbol": req.symbol,
        "timeframe": req.timeframe,
    }
