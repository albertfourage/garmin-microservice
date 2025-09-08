import os
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from garminconnect import Garmin

# Defaults used only as a last resort if GARMINTOKENS isn't exported by start.sh
DEFAULT_TOKENS_DIR = "/data/garmin_tokens"
DEFAULT_TOKENS_FILE = "/data/garmintokens.json"


class GarminClient:
    """
    Thin wrapper around garminconnect.Garmin with:
    - Flexible token loading (two-file dir or single-file JSON)
    - Optional credential fallback to refresh tokens if needed
    - Convenience getters used by the FastAPI handlers
    """

    def __init__(self) -> None:
        # Optional creds (for bootstrap/refresh only)
        self.email = os.getenv("GARMIN_EMAIL")
        self.password = os.getenv("GARMIN_PASSWORD")

        # start.sh should export GARMINTOKENS to a dir (two files) or file (single JSON)
        tokens_env = os.getenv("GARMINTOKENS")
        if not tokens_env:
            # Fallbacks in case someone bypassed start.sh (e.g., local runs)
            if os.path.isdir(DEFAULT_TOKENS_DIR):
                tokens_env = DEFAULT_TOKENS_DIR
            else:
                tokens_env = DEFAULT_TOKENS_FILE
        os.environ["GARMINTOKENS"] = tokens_env

        self._client: Optional[Garmin] = None

    def _load(self) -> None:
        """
        Initialize and login. Prefer tokens. If tokens fail and creds are present,
        retry to create/refresh tokens.
        """
        # When email/password are empty strings, Garmin() still loads tokens from env path
        self._client = Garmin(self.email or "", self.password or "")

        try:
            # First attempt: token-based login
            self._client.login()
        except Exception as first_err:
            # If no creds available, surface a helpful error early
            if not (self.email and self.password):
                raise RuntimeError(
                    "Garmin tokens missing/invalid and no credentials provided. "
                    "Supply OAUTH1_TOKEN_JSON + OAUTH2_TOKEN_JSON via env (preferred), "
                    "or set GARMIN_EMAIL/GARMIN_PASSWORD locally for a one-time bootstrap."
                ) from first_err

            # Retry with provided credentials to refresh tokens
            self._client = Garmin(self.email, self.password)
            self._client.login()  # will raise if still failing

    def close(self) -> None:
        try:
            if self._client:
                self._client.logout()
        except Exception:
            # Be tolerant on shutdown
            pass

    # ------------- Convenience getters used by your routes -----------------

    def _safe(self, fn):
        try:
            return fn()
        except Exception:
            return {}

    def get_user_hrmax(self) -> Optional[int]:
        try:
            prof = self._client.get_user_profile()
            return (prof or {}).get("userMetricsProfile") or {}.get("maxHeartRate")
        except Exception:
            # Some accounts expose HRmax in different endpoints; fall back to None
            return None

    def get_lthr_run(self) -> Optional[int]:
        try:
            zones = self._client.get_heart_rate_zones()
            # Heuristic: lactate threshold often provided in "lactateThresholdHeartRate"
            return (zones or {}).get("lactateThresholdHeartRate")
        except Exception:
            return None

    def get_lthr_cycle(self) -> Optional[int]:
        try:
            cycling = self._client.get_cycling_heart_rate_zones()
            return (cycling or {}).get("lactateThresholdHeartRate")
        except Exception:
            return None

    def get_ftp(self) -> Optional[int]:
        try:
            ftp = self._client.get_ftp()
            # library may return dict or list; normalize
            if isinstance(ftp, dict):
                return ftp.get("currentFTP") or ftp.get("ftp")
            if isinstance(ftp, list) and ftp:
                return ftp[0].get("currentFTP") or ftp[0].get("ftp")
        except Exception:
            pass
        return None

    def estimate_threshold_pace_seconds(self) -> Optional[float]:
        """
        Optional helper if you had one before. This just returns None unless you
        compute it from recent activities. Keep or replace with your prior logic.
        """
        try:
            # Example heuristic (very conservative): use best 10k pace in last 90 days
            today = date.today()
            start = date.fromordinal(today.toordinal() - 90)
            acts = self.get_activities_range(start, today)
            best = None
            for a in acts or []:
                if a.get("activityTypeDTO", {}).get("typeKey") != "running":
                    continue
                dist = (a.get("distance") or 0.0)  # meters
                dur = (a.get("duration") or 0.0)   # seconds
                if dist >= 10000 and dur > 0:
                    pace = dur / (dist / 1000.0)  # sec/km
                    best = pace if best is None else min(best, pace)
            return best
        except Exception:
            return None

    def get_latest_weight(self) -> Optional[float]:
        try:
            w = self._client.get_body_composition(date.today().strftime("%Y-%m-%d"))
            return (w or {}).get("weight")
        except Exception:
            return None

    def get_activities_range(self, start: date, end: date) -> List[Dict[str, Any]]:
        """
        Return raw activities within [start, end]. Adjust to your preferred pagination.
        """
        items: List[Dict[str, Any]] = []
        try:
            # Pull in batches; garminconnect typically paginates by index/limit
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")
            # If your previous implementation used a different method, keep that.
            page = 0
            page_size = 100
            while True:
                batch = self._client.get_activities_by_date(
                    start_str, end_str, limit=page_size, start=page * page_size
                )
                if not batch:
                    break
                items.extend(batch)
                if len(batch) < page_size:
                    break
                page += 1
        except Exception:
            pass
        return items

    def get_activity_steps(self, activity_id: int) -> Dict[str, Any]:
        try:
            return self._client.get_activity_splits(activity_id) or {}
        except Exception:
            return {}

    def get_daily_kpis(self, d: date) -> Dict[str, Any]:
        ds = d.strftime("%Y-%m-%d")
        out: Dict[str, Any] = {}
        try:
            out["summary"] = self._client.get_user_summary(ds)
        except Exception:
            out["summary"] = {}
        try:
            out["hrv"] = self._client.get_hrv_data(ds)
        except Exception:
            out["hrv"] = {}
        try:
            out["sleep"] = self._client.get_sleep_data(ds)
        except Exception:
            out["sleep"] = {}
        try:
            out["stress"] = self._client.get_stress_data(ds)
        except Exception:
            out["stress"] = {}
        return out


@contextmanager
def get_gc():
    gc = GarminClient()
    gc._load()
    try:
        yield gc
    finally:
        gc.close()
