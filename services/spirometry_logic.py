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
    def pct_pred_pre(self):
        if self.measured_pre is None or self.predicted in (None, 0):
            return None
        return (self.measured_pre / self.predicted) * 100

    @property
    def pct_pred_post(self):
        if self.measured_post is None or self.predicted in (None, 0):
            return None
        return (self.measured_post / self.predicted) * 100
