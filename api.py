import csv
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from scanner_service import ScannerService


app = FastAPI(title="Triangular Arbitrage Monitor", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
service = ScannerService()


class ConfigRequest(BaseModel):
    starting_amount: float = Field(gt=0)
    fee_rate: float = Field(ge=0, le=1)
    safety_threshold_pct: float = Field(ge=0, le=100)
    poll_interval_seconds: int = Field(ge=1, le=3600)


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "observation-only", "real_orders": False}


@app.get("/api/status")
def status():
    return service.status()


@app.post("/api/scan")
def scan():
    try:
        return service.scan_once()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Public market data scan failed: {exc}") from exc


@app.post("/api/monitor/start")
def start_monitoring():
    return {"running": service.start() or service.is_running()}


@app.post("/api/monitor/stop")
def stop_monitoring():
    service.stop()
    return {"running": service.is_running()}


@app.post("/api/config")
def update_config(config: ConfigRequest):
    try:
        service.update_config(**config.model_dump())
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return service.serialized_config()


@app.get("/api/observations")
def observations(
    route: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    filename = Path(service.observation_file)
    if not filename.exists():
        return {"observations": []}
    with filename.open(newline="") as file:
        rows = list(csv.DictReader(file))
    if route:
        rows = [row for row in rows if row.get("route") == route]
    if status_filter:
        rows = [row for row in rows if row.get("status") == status_filter]
    return {"observations": list(reversed(rows[-limit:]))}

