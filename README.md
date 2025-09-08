# Garmin Microservice (FastAPI + Railway)

Fetch Activities, Steps, Daily KPIs, and live Parameters from Garmin Connect for n8n → Google Sheets.

Endpoints (all require `X-API-Key` unless API_KEY unset)
- GET /health
- GET /params
- GET /activities?start=YYYY-MM-DD&end=YYYY-MM-DD
- GET /activity/{activityId}/steps
- GET /daily?date=YYYY-MM-DD

Quick start (Windows 10)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Bootstrap tokens (one-time):
$env:GARMINTOKENS_PATH = "$PWD\tokens.json"
$env:GARMIN_EMAIL="you@example.com"; $env:GARMIN_PASSWORD="your_password"
python - << 'PY'
from garminconnect import Garmin
import os
os.environ["GARMINTOKENS"]=os.getenv("GARMINTOKENS_PATH")
g=Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD")); g.login()
print("Tokens saved to:", os.environ["GARMINTOKENS"])
PY
# Run locally
$env:API_KEY="dev-key"
$env:GARMINTOKENS_JSON=(Get-Content "$PWD\tokens.json" -Raw)
uvicorn app.main:app --reload
```

Deploy on Railway
- Create project from this repo, set variables:
  - API_KEY, TZ=Europe/Bratislava
  - GARMINTOKENS_JSON: paste the contents of your local tokens.json
- Deploy → test `/health` and `/params`.

Legal: For personal use. For commercial/large-scale, apply to Garmin Connect Developer Program.
