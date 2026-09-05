"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.auth.router import router as auth_router
from app.blockchain.router import router as blockchain_router
from app.core.config import settings
from app.hives.router import router as hive_router
from app.lab.router import router as lab_router
from app.packaging.router import router as packaging_router
from app.risk.router import router as risk_router
from app.telemetry.router import router as telemetry_router
from app.traceability.router import router as traceability_router

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(hive_router)
app.include_router(telemetry_router)
app.include_router(risk_router)
app.include_router(traceability_router)
app.include_router(lab_router)
app.include_router(blockchain_router)
app.include_router(packaging_router)
