import numpy as np
import logging

logger = logging.getLogger(__name__)


def apply_offset_correction(raw: dict, meas_name: str, ref_name: str) -> None:
    if meas_name not in raw or ref_name not in raw:
        logger.warning(f"AVL offset correction skipped: missing {meas_name} or {ref_name}")
        return

    meas = raw[meas_name]
    ref = raw[ref_name]
    m_data = np.asarray(meas["data"], dtype=float)
    r_data = np.asarray(ref["data"], dtype=float)
    m_axis = np.asarray(meas["axis"], dtype=float)
    r_axis = np.asarray(ref["axis"], dtype=float)

    if m_data.ndim != 2 or r_data.ndim != 2:
        raise ValueError(f"Expected 2D arrays for {meas_name} and {ref_name}, got {m_data.shape} and {r_data.shape}")

    m_n, n_cycles_m = m_data.shape
    r_n, n_cycles_r = r_data.shape
    if n_cycles_m != n_cycles_r:
        raise ValueError(f"Cycle count mismatch: {meas_name} has {n_cycles_m}, {ref_name} has {n_cycles_r}")

    n_cycles = n_cycles_m
    per_cycle_offset = np.zeros(n_cycles, dtype=float)

    for c in range(n_cycles):
        m_cycle = m_data[:, c]
        r_cycle = r_data[:, c]
        
        m_interp = np.interp(r_axis, m_axis, m_cycle, left=np.nan, right=np.nan)
        diff = r_cycle - m_interp
        valid = ~np.isnan(diff)
        if not np.any(valid):
            per_cycle_offset[c] = 0.0
        else:
            per_cycle_offset[c] = float(np.nanmean(diff[valid]))

    mean_valid = float(np.nanmean(per_cycle_offset))
    logger.debug(f"Applied offset correction for '{meas_name}' using '{ref_name}'. mean_offset={mean_valid}")

    corrected = m_data + per_cycle_offset
    meas["data"] = corrected
