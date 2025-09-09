import os
from datetime import date, datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Header
from app.garmin_client import get_gc
from app.utils import parse_date

API_KEY = os.getenv("API_KEY", "")

app = FastAPI(title="Garmin Microservice", version="1.0.0")

def require_api_key(x_api_key: Optional[str] = Header(None)):
    if not API_KEY:
        return  # dev mode
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat() + "Z"}

@app.get("/params")
def params_guarded(_: None = Depends(require_api_key)):
    with get_gc() as gc:
        today = date.today()
        # Resting HR
        hr = gc._safe(lambda: gc._client.get_heart_rates(today.strftime("%Y-%m-%d"))) or {}
        rhr = hr.get("restingHeartRate", None)
        hrmax = hr.get("maxHeartRate", None)
        # VO2max
        vo2 = gc._safe(lambda: gc._client.get_vo2max()) or {}
        vo2_value = vo2.get("vo2MaxValue")
        # Thresholds & FTP
        out = {
            "HRmax": hrmax,
            "HRrest": rhr,
            "LTHR_run": gc.get_lthr_run(),
            "LTHR_cycle": gc.get_lthr_cycle(),
            "FTP_bike_W": gc.get_ftp(),
            "rThreshold_pace_s_per_km": gc.estimate_threshold_pace_seconds(),
            "VO2max": vo2_value,
            "weight_kg": gc.get_latest_weight(),
            "updated_at": today.isoformat(),
            "source": "GarminConnect"
        }
        return out

@app.get("/activities")
def activities(start: str, end: str, _: None = Depends(require_api_key)):
    d0 = parse_date(start); d1 = parse_date(end)
    with get_gc() as gc:
        items = gc.get_activities_range(d0, d1)
        return {"items": items}

@app.get("/activity/{activity_id}/steps")
def activity_steps(activity_id: int, _: None = Depends(require_api_key)):
    with get_gc() as gc:
        return {"activity_id": activity_id, "steps": gc.get_activity_steps(activity_id)}

@app.get("/daily")
def daily(date_str: str, _: None = Depends(require_api_key)):
    d = parse_date(date_str)
    with get_gc() as gc:
        data = gc.get_daily_kpis(d)
        data["date"] = d.isoformat()
        return data
