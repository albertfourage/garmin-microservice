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
        self._client = Garmin(self.email or "", self.password or "")

        try:
            self._client.login()
        except Exception as first_err:
            if not (self.email and self.password):
                raise RuntimeError(
                    "Garmin tokens missing/invalid and no credentials provided. "
                    "Supply OAUTH1_TOKEN_JSON + OAUTH2_TOKEN_JSON via env (preferred), "
                    "or set GARMIN_EMAIL/GARMIN_PASSWORD locally for a one-time bootstrap."
                ) from first_err

            self._client = Garmin(self.email, self.password)
            self._client.login()
    def close(self) -> None:
        try:
            if self._client:
                self._client.logout()
        except Exception:
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
            metrics = (prof or {}).get("userMetricsProfile", {})
            return metrics.get("maxHeartRate")
        except Exception:
            return None

    def get_lthr_run(self) -> Optional[int]:
        """Extracts lactate threshold heart rate for running from heart rate zones."""
        try:
            zones = self._client.get_heart_rate_zones()
            if isinstance(zones, dict):
                return zones.get("lactateThresholdHeartRate")
        except Exception:
            pass
            return None

    def get_lthr_cycle(self) -> Optional[int]:
        """Extracts lactate threshold heart rate for cycling from cycling heart rate zones."""
        try:
            cycling = self._client.get_cycling_heart_rate_zones()
            if isinstance(cycling, dict):
                return cycling.get("lactateThresholdHeartRate")
        except Exception:
            pass
        return None

    def get_ftp(self) -> Optional[int]:
        try:
            ftp = self._client.get_ftp()
            if isinstance(ftp, dict):
                return ftp.get("currentFTP") or ftp.get("ftp")
            if isinstance(ftp, list) and ftp:
                return ftp[0].get("currentFTP") or ftp[0].get("ftp")
        except Exception:
            pass
            return None

    def get_vo2max(self) -> Optional[float]:
        """Extracts VO2max value from the Garmin API. Returns None if not present."""
        try:
            result = self._client.get_vo2max()
            if isinstance(result, dict):
                return result.get("vo2MaxValue")
        except Exception:
            pass
        return None

    def estimate_threshold_pace_seconds(self) -> Optional[float]:
        try:
            today = date.today()
            start = date.fromordinal(today.toordinal() - 90)
            acts = self.get_activities_range(start, today)
            best = None
            for a in acts or []:
                if a.get("activityTypeDTO", {}).get("typeKey") != "running":
                    continue
                dist = (a.get("distance") or 0.0)
                dur = (a.get("duration") or 0.0)
                if dist >= 10000 and dur > 0:
                    pace = dur / (dist / 1000.0)
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
        items: List[Dict[str, Any]] = []
        try:
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")
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

