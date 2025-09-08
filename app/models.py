from pydantic import BaseModel
from typing import Optional

class ParamsResponse(BaseModel):
    HRmax: Optional[int]
    HRrest: Optional[int]
    LTHR_run: Optional[int]
    LTHR_cycle: Optional[int]
    FTP_bike_W: Optional[int]
    rThreshold_pace_s_per_km: Optional[float]
    VO2max: Optional[float]
    weight_kg: Optional[float]
    updated_at: str
    source: str
