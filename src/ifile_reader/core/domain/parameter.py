from __future__ import annotations
import numpy as np
from collections.abc import Mapping
from typing import Any
from ifile_reader.core.domain.dependencies import GeneralView


def _extract_param_components(pname: str, p) -> tuple[float, str, str]:
    val = float("nan")
    unit = "-"
    desc = ""
    if p is None:
        return val, unit, desc
    if isinstance(p, dict) and pname.upper() == "TIMESTAMP":
        val = p.get("value") or (p.get("values")[0] if "values" in p else None)
        unit = p.get("unit", "-")
        desc = p.get("description", "")
        return val, unit, desc
    if isinstance(p, dict):
        if "value" in p:
            val = p["value"]
        elif "values" in p:
            v = p["values"]
            try:
                if hasattr(v, "__len__") and np.asarray(v).size == 1:
                    val = float(np.asarray(v).reshape(-1)[0])
                else:
                    val = float(np.asarray(v).reshape(-1)[0]) if len(v) > 0 else float("nan")
            except Exception:
                try:
                    val = float(v)
                except Exception:
                    val = float("nan")
        else:
            try:
                val = float(p)
            except Exception:
                val = float("nan")

        unit = p.get("unit", p.get("units", "-"))
        desc = p.get("description", "")
        try:
            val = float(val)
        except Exception:
            try:
                if hasattr(val, "item"):
                    val = float(np.asarray(val).item())
                else:
                    val = float("nan")
            except Exception:
                val = float("nan")
        return val, unit, desc

    val_attr = getattr(p, "values", None)
    if val_attr is None:
        val_attr = getattr(p, "value", None)
    try:
        if val_attr is not None:
            val = float(val_attr)
        else:
            val = float(p)
    except Exception:
        try:
            if hasattr(val_attr, "__len__") and np.asarray(val_attr).size == 1:
                val = float(np.asarray(val_attr).reshape(-1)[0])
            else:
                val = float("nan")
        except Exception:
            val = float("nan")

    unit = getattr(p, "unit", None) or getattr(p, "units", None)
    desc = getattr(p, "description", "")
    return val, unit, desc


class ParameterValuesView(Mapping):
    def __init__(self, mapping: dict[str, Any], pname: str):
        self._map = mapping
        self._pname = pname

    def __getitem__(self, key: str):
        return self._map[key]

    def __iter__(self):
        return iter(self._map)

    def __len__(self):
        return len(self._map)

    def keys(self):
        return self._map.keys()

    def items(self):
        return self._map.items()

    def __repr__(self):
        parts = []
        for k, v in self._map.items():
            if isinstance(v, np.ndarray):
                s = np.array2string(v, max_line_width=80, threshold=6, precision=6, separator=", ")
            else:
                s = repr(v)
            parts.append(f"'{k}': {s}")
        return "{" + ", ".join(parts) + "}"


class ParameterView:
    @property
    def general(self):
        """
        Attribute-access view of channel GENERAL metadata.
        """
        return GeneralView.from_dict(self["GENERAL"])

    @property
    def values(self):
        """
        Shorthand for channel['VALUES'].
        """
        return self["VALUES"]
    
    def __init__(self, pname: str, pblock, test_name: str | None = None):
        self._name = pname
        self._block = pblock
        self._test = test_name or ""

    def __getitem__(self, key: str):
        ku = key.upper()
        if ku == "GENERAL":
            return self._build_general()
        if ku == "VALUES":
            return self._build_values()
        raise KeyError(f"Parameter '{self._name}' has no key '{key}'")

    def _build_general(self) -> dict:
        val, unit, desc = _extract_param_components(self._name, self._block)
        return {
            "Channel": self._name,
            "Units": unit or "-",
            "Description": desc or "",
            "Base": "",
            "RecordCount": 1,
            "Range": "",
            "Test": self._test or "",
        }

    def _build_values(self) -> ParameterValuesView:
        val, _, _ = _extract_param_components(self._name, self._block)
        idx_arr = np.array([0])
        if isinstance(val, str):
            val_arr = np.array([val], dtype=object)
        else:
            val_arr = np.array([val], dtype=float)
        mapping = {"": idx_arr, self._name: val_arr}
        return ParameterValuesView(mapping, self._name)

    def __repr__(self):
        try:
            return ("{'GENERAL': " + repr(self._build_general()) + ", 'VALUES': " + repr(self._build_values()) + "}")
        except Exception:
            return f"<ParameterView {self._name}>"


class ParameterIndex(Mapping):
    def __init__(self, ifile):
        self._ifile = ifile

    def __repr__(self):
        try:
            params = self._ifile._raw.get("parameters") or self._ifile._raw.get("PAR")
            return repr(sorted(params.keys(), key=str.lower))
        except Exception:
            return "[]"

    def __len__(self):
        params = self._ifile._raw.get("parameters") or self._ifile._raw.get("PAR")
        return len(params)

    def __iter__(self):
        params = self._ifile._raw.get("parameters") or self._ifile._raw.get("PAR")
        return iter(params)

    def __getitem__(self, key: str):
        params = self._ifile._raw.get("parameters") or self._ifile._raw.get("PAR")
        if key not in params:
            raise KeyError(f"Parameter '{key}' not found")
        test_name = str(self._ifile.path) if hasattr(self._ifile, "path") else self._ifile._raw.get("_test", "")
        return ParameterView(key, params[key], test_name)
