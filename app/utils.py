from datetime import datetime, date

def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def to_iso(dt: datetime) -> str:
    return dt.isoformat() + "Z"

def mm_ss_per_km(seconds: float) -> str:
    if not seconds:
        return ""
    m = int(seconds // 60)
    s = int(round(seconds % 60))
    return f"{m}:{s:02d}"
