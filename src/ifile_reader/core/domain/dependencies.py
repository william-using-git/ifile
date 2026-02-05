import numpy as np
from dataclasses import dataclass
from typing import Optional


def _classify_axis(axis: np.ndarray) -> str:
    if axis.size < 2:
        return "CY"

    axis = np.asarray(axis, dtype=float)
    amin = float(np.nanmin(axis))
    diffs = np.diff(axis)
    step = float(np.nanmedian(diffs)) if diffs.size else 0.0

    if amin < 0 or abs(step) < 0.5:
        return "CA"
    return "CY"


def _format_range_from_axis(axis: np.ndarray, unit: str) -> str:
    if axis.size < 2:
        return ""
    try:
        a0 = float(axis[0])
        a1 = float(axis[-1])
        diffs = np.diff(axis.astype(float))
        step = float(np.nanmedian(diffs)) if diffs.size else 0.0
        return f"{a0:g}[{unit}] to {a1:g} step {step:g}"
    except Exception:
        return ""


@dataclass
class GeneralView:
    channel: str
    units: str
    description: str
    base: str
    record_count: int
    range: str
    test: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            channel=d.get("Channel", ""),
            units=d.get("Units", ""),
            description=d.get("Description", ""),
            base=d.get("Base", ""),
            record_count=d.get("RecordCount", 0),
            range=d.get("Range", ""),
            test=d.get("Test", None),
        )