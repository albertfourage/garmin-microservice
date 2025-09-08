import json, os, pathlib
from contextlib import contextmanager
from datetime import date
from typing import Any, Dict, List, Optional

from garminconnect import Garmin

TOKENS_ENV = "GARMINTOKENS_JSON"
TOKENS_PATH_ENV = "GARMINTOKENS_PATH"
DEFAULT_TOKENS_FILE = "/data/garmintokens.json"

class GarminClient:
    def __init__(self):
        self.email = os.getenv("GARMIN_EMAIL")
        self.password = os.getenv("GARMIN_PASSWORD")
        self._client: Optional[Garmin] = None

        self.tokens_path = os.getenv(TOKENS_PATH_ENV, DEFAULT_TOKENS_FILE)
        os.makedirs(os.path.dirname(self.tokens_path), exist_ok=True)

        blob = os.getenv(TOKENS_ENV)
        if blob and not os.path.exists(self.tokens_path):
            with open(self.tokens_path, "w", encoding="utf-8") as f:
                f.write(blob)

    def _load(self):
        self._client = Garmin(self.email or "", self.password or "")
        os.environ["GARMINTOKENS"] = self.tokens_path
        try:
            self._client.login()
        except Exception as e:
            if not (self.email and self.password):
                raise RuntimeError("Garmin tokens missing and no credentials supplied. "
                                   "Run local token bootstrap or set GARMIN_EMAIL/PASSWORD.") from e
            self._client.login()

    def close(self):
        try:
            self._client.logout()
        except Exception:
            pass

    # -------- Public API --------

    def get_activities_range(self, d0: date, d1: date) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        try:
            items = self._client.get_activities_by_date(d0.strftime("%Y-%m-%d"),
                                                        d1.strftime("%Y-%m-%d"))
        except AttributeError:
            recent = self._client.get_activities(0, 400)
            def within(r):
                st = r.get("startTimeLocal") or r.get("startTimeGMT")
                return bool(st and (st[:10] >= d0.isoformat()) and (st[:10] <= d1.isoformat()))
            items = [self._map_activity(a) for a in recent if within(a)]
        if items and "activityId" in items[0]:
            items = [self._map_activity(a) for a in items]
        return items

    def get_activity_steps(self, activity_id: int) -> List[Dict[str, Any]]:
        details = self._client.get_activity_details(activity_id)
        out = []
        for i, s in enumerate(details.get("activityDetailMetrics", []) or []):
            out.append({
                "activity_id": activity_id,
                "index": i,
                "metric_type": s.get("metricType", ""),
                "start_offset_s": s.get("startTimeInSeconds"),
                "end_offset_s": s.get("endTimeInSeconds"),
                "distance_m": s.get("distanceInMeters"),
                "avg_hr": s.get("averageHR"),
                "max_hr": s.get("maxHR"),
                "avg_power_w": s.get("averagePower"),
                "cadence": s.get("averageRunCadence") or s.get("averageCyclingCadence"),
                "elevation_gain_m": s.get("elevationGain"),
                "elevation_loss_m": s.get("elevationLoss"),
            })
        return out

    def get_daily_kpis(self, d: date) -> Dict[str, Any]:
        ds = d.strftime("%Y-%m-%d")
        out: Dict[str, Any] = {}

        sleep = self._safe(lambda: self._client.get_sleep_data(ds))
        ss = (sleep or [{}])[0] if isinstance(sleep, list) else (sleep or {})
        out.update({
            "sleep_score": ss.get("overallSleepScore"),
            "sleep_duration_min": _mins(ss.get("sleepTimeSeconds")),
            "sleep_efficiency": ss.get("sleepEfficiency"),
            "sleep_awake_min": _mins(ss.get("awakeSleepSeconds")),
            "sleep_light_min": _mins(ss.get("lightSleepSeconds")),
            "sleep_deep_min": _mins(ss.get("deepSleepSeconds")),
            "sleep_rem_min": _mins(ss.get("remSleepSeconds")),
        })

        hr = self._safe(lambda: self._client.get_heart_rates(ds)) or {}
        hrv = self._safe(lambda: self._client.get_hrv_data(ds)) or {}
        bb = self._safe(lambda: self._client.get_body_battery(ds)) or {}
        stress = self._safe(lambda: self._client.get_stress_data(ds)) or {}
        out.update({
            "hrv_avg_ms": (hrv.get("hrvSummary", {}) or {}).get("lastNightAvg"),
            "hrv_status": (hrv.get("hrvSummary", {}) or {}).get("status"),
            "hrv_baseline_7d_ms": (hrv.get("hrvSummary", {}) or {}).get("weeklyAverage"),
            "resting_hr_bpm": hr.get("restingHeartRate"),
            "body_battery_start": (bb.get("bodyBattery", {}) or {}).get("chargedLevel"),
            "body_battery_end": (bb.get("bodyBattery", {}) or {}).get("drainedLevel"),
            "stress_daily_avg": (stress.get("stressQualitative", {}) or {}).get("currentDayStressScore"),
        })

        ts = self._safe(lambda: self._client.get_training_status()) or {}
        out.update({
            "training_status": (ts.get("trainingStatus", {}) or {}).get("trainingStatus"),
            "training_trend": (ts.get("trainingStatus", {}) or {}).get("trainingTrend"),
            "recovery_time_hours": (ts.get("recoveryTimeDTO", {}) or {}).get("value"),
            "acute_load_value": (ts.get("trainingLoad", {}) or {}).get("value"),
            "acute_load_opt_low": (ts.get("trainingLoad", {}) or {}).get("optimalRangeLow"),
            "acute_load_opt_high": (ts.get("trainingLoad", {}) or {}).get("optimalRangeHigh"),
            "load_low_aerobic": (ts.get("aerobicTrainingEffect", {}) or {}).get("value"),
            "load_high_aerobic": (ts.get("anaerobicTrainingEffect", {}) or {}).get("value"),
        })

        vo2 = self._safe(lambda: self._client.get_vo2max()) or {}
        out.update({
            "vo2max_value": vo2.get("vo2MaxValue"),
            "vo2max_fitness_age": vo2.get("fitnessAge"),
        })

        out.update({
            "lthr_run_bpm": self.get_lthr_run(),
            "lthr_cycle_bpm": self.get_lthr_cycle(),
            "est_max_hr_bpm": self.get_user_hrmax(),
        })
        return out

    def get_user_hrmax(self) -> Optional[int]:
        try:
            settings = self._client.get_full_user_profile()
            return (settings.get("userInfo", {}) or {}).get("maxHeartRate")
        except Exception:
            return None

    def get_ftp(self) -> Optional[int]:
        try:
            perf = self._client.get_performance_condition()
            if perf and isinstance(perf, dict) and "cyclingFtp" in perf:
                return perf.get("cyclingFtp")
        except Exception:
            pass
        try:
            settings = self._client.get_user_settings()
            return (settings.get("cycling") or {}).get("ftp")
        except Exception:
            return None

    def get_lthr_run(self) -> Optional[int]:
        try:
            th = self._client.get_lactate_threshold()
            return th.get("runLthr") or th.get("lthr")
        except Exception:
            return None

    def get_lthr_cycle(self) -> Optional[int]:
        try:
            th = self._client.get_lactate_threshold()
            return th.get("cycleLthr") or th.get("cyclingLthr")
        except Exception:
            return None

    def get_latest_weight(self) -> Optional[float]:
        try:
            w = self._client.get_body_composition(date.today().strftime("%Y-%m-%d"))
            if isinstance(w, list) and w:
                return w[-1].get("weight")
            if isinstance(w, dict):
                return w.get("weight")
        except Exception:
            return None

    def estimate_threshold_pace_seconds(self) -> Optional[float]:
        try:
            lt = self._client.get_lactate_threshold()
            pace = lt.get("runThresholdPace") or lt.get("pace")
            if pace:
                if isinstance(pace, str) and ":" in pace:
                    m, s = pace.split(":")
                    return int(m) * 60 + int(s)
                if isinstance(pace, (float, int)):
                    return float(pace)
        except Exception:
            pass
        try:
            recent = self._client.get_activities(0, 50)
            runs = [a for a in recent if a.get("activityType", {}).get("typeKey") == "running"]
            best = None
            for a in runs:
                mdur = a.get("movingDuration") or a.get("duration")
                if mdur and 2700 <= mdur <= 5400:
                    dist_m = a.get("distance")
                    if dist_m:
                        pace = (mdur / (dist_m / 1000.0))
                        if best is None or pace < best:
                            best = pace
            return best
        except Exception:
            return None

    def _map_activity(self, a: Dict[str, Any]) -> Dict[str, Any]:
        atype = (a.get("activityType") or {}).get("typeKey") or a.get("activityTypeDTO", {}).get("typeKey")
        name = a.get("activityName") or a.get("activityNameDTO", {}).get("displayName")
        avg_pace_s_per_km = None
        avg_speed = a.get("averageSpeed")
        dist_m = a.get("distance")
        if avg_speed:
            avg_pace_s_per_km = _pace_sec_per_km(avg_speed)
        elif dist_m and a.get("movingDuration"):
            avg_pace_s_per_km = a["movingDuration"] / (dist_m / 1000.0)
        return {
            "id": a.get("activityId"),
            "start_time_local": a.get("startTimeLocal"),
            "start_time_utc": a.get("startTimeGMT"),
            "activity_type": atype.upper() if atype else None,
            "name": name,
            "duration_s": a.get("duration"),
            "moving_duration_s": a.get("movingDuration"),
            "distance_m": dist_m,
            "elevation_gain_m": a.get("elevationGain"),
            "elevation_loss_m": a.get("elevationLoss"),
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
            "avg_cadence": a.get("averageRunCadence") or a.get("averageCyclingCadence"),
            "avg_power_w": a.get("averagePower"),
            "max_power_w": a.get("maxPower"),
            "np_w": a.get("normalizedPower"),
            "avg_pace_s_per_km": avg_pace_s_per_km,
            "avg_speed_mps": a.get("averageSpeed"),
            "calories": a.get("calories"),
            "vo2max_value": a.get("vO2MaxValue"),
            "aerobic_te": a.get("aerobicTrainingEffect"),
            "anaerobic_te": a.get("anaerobicTrainingEffect"),
            "training_load_epoc": a.get("trainingLoad"),
            "avg_temperature_c": a.get("averageTemperature"),
            "min_temperature_c": a.get("minTemperature"),
            "max_temperature_c": a.get("maxTemperature"),
            "stride_length_m": a.get("strideLength"),
            "vertical_osc_mm": a.get("verticalOscillation"),
            "avg_grade_percent": a.get("avgGrade") or a.get("avgGradeAdjusted"),
            "avg_vam": a.get("avgVerticalSpeed"),
            "avg_run_cadence": a.get("averageRunCadence"),
            "device": (a.get("deviceMetaDataDTO") or {}).get("deviceId"),
            "source": "GarminConnect",
            "note": "",
        }

    def _safe(self, fn):
        try:
            return fn()
        except Exception:
            return {}

def _pace_sec_per_km(speed_mps):
    if not speed_mps or speed_mps <= 0:
        return None
    return 1000.0 / speed_mps

@contextmanager
def get_gc():
    gc = GarminClient()
    gc._load()
    try:
        yield gc
    finally:
        gc.close()
