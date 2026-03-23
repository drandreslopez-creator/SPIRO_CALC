# services/spirometry_logic.py

from dataclasses import dataclass
from typing import Optional


@dataclass
class ParameterResult:
    name: str
    unit: str
    measured_pre: Optional[float]
    measured_post: Optional[float]
    predicted: Optional[float]
    lln: Optional[float]
    zscore_pre: Optional[float]
    zscore_post: Optional[float]

    @property
    def pct_pred_pre(self) -> Optional[float]:
        if self.measured_pre is None or self.predicted in (None, 0):
            return None
        return (self.measured_pre / self.predicted) * 100

    @property
    def pct_pred_post(self) -> Optional[float]:
        if self.measured_post is None or self.predicted in (None, 0):
            return None
        return (self.measured_post / self.predicted) * 100

    @property
    def delta_abs(self) -> Optional[float]:
        if self.measured_pre is None or self.measured_post is None:
            return None
        return self.measured_post - self.measured_pre

    @property
    def delta_pct_baseline(self) -> Optional[float]:
        if self.measured_pre in (None, 0) or self.measured_post is None:
            return None
        return ((self.measured_post - self.measured_pre) / self.measured_pre) * 100