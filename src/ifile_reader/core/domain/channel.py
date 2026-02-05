from __future__ import annotations
import numpy as np
from typing import Any
from collections.abc import Mapping
from ifile_reader.core.domain.dependencies import GeneralView, _classify_axis, _format_range_from_axis


def _safe_str(x: Any, default: str = "") -> str:
    if x is None:
        return default
    try:
        return str(x)
    except Exception:
        return default


def _build_channel_general(name: str, block: dict[str, Any], test_name: str | None = None) -> dict[str, Any]:
    axis = np.asarray(block.get("axis", np.asarray([])))
    axis_type = _classify_axis(axis)
    if axis_type == "CA":
        base = "Crank Angle"
        unit_for_range = "deg"
    else:
        base = "Cycle"
        unit_for_range = "-"

    unit = _safe_str(block.get("units", "-"), "-")
    desc = _safe_str(block.get("description", ""))
    rng = _format_range_from_axis(axis, unit_for_range)
    rec_cnt = int(np.asarray(block.get("data", [])).reshape(-1).size)
    g = {
        "Channel": name,
        "Units": unit,
        "Description": desc,
        "Base": base,
        "RecordCount": rec_cnt,
        "Range": rng,
    }
    if test_name is not None:
        g["Test"] = test_name
    return g


class ValuesView(Mapping):
    def __init__(self, mapping: dict[str, np.ndarray]):
        self._map = mapping

    def __getitem__(self, key: str) -> np.ndarray:
        return self._map[key]

    def __iter__(self):
        return iter(self._map)

    def __len__(self) -> int:
        return len(self._map)

    def keys(self):
        return self._map.keys()

    def items(self):
        return self._map.items()

    def __repr__(self) -> str:
        parts = []
        for k, v in self._map.items():
            arr = np.asarray(v)
            s = np.array2string(
                arr,
                max_line_width=120,
                threshold=20,
                precision=6,
                separator=", ",
            )
            parts.append(f"'{k}': {s}")
        return "{" + ", ".join(parts) + "}"


class ChannelView:
    @property
    def general(self) -> GeneralView:
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
    
    def __init__(self, name: str, channel_block: dict[str, Any], test_name: str | None = None):
        self._name = name
        self._block = channel_block or {}
        self._test = test_name

    def _raw_data(self) -> np.ndarray:
        return np.asarray(self._block.get("data", np.asarray([])))

    def __array__(self, dtype=None):
        arr = self._flatten_primary()
        return arr.astype(dtype) if dtype is not None else arr

    def __getitem__(self, key):
        if isinstance(key, str):
            ku = key.upper()
            if ku == "GENERAL":
                return _build_channel_general(self._name, self._block, self._test)
            if ku == "VALUES":
                mapping = self._build_values_mapping()
                return ValuesView(mapping)

            lk = key.lower()
            if lk in self._block:
                return self._block[lk]
            if key in self._block:
                return self._block[key]
            raise KeyError(f"Channel '{self._name}' has no attribute/key '{key}'")
        return self._flatten_primary()[key]

    def _flatten_primary(self) -> np.ndarray:
        data = np.asarray(self._block.get("data", np.asarray([])))
        axis = np.asarray(self._block.get("axis", np.asarray([])))
        if data.size == 0:
            return np.asarray([])

        if data.ndim == 1:
            return data.reshape(-1)

        if data.ndim == 2:
            if axis.size == data.shape[1]:
                return data.reshape(-1)
            if axis.size == data.shape[0]:
                return data.T.reshape(-1)
            return data.reshape(-1)

        if data.ndim >= 3:
            axis_dim = None
            for i, s in enumerate(data.shape):
                if s == axis.size and axis.size > 0:
                    axis_dim = i
                    break
            if axis_dim is not None:
                d2 = np.moveaxis(data, axis_dim, -1)
                return d2.reshape(-1)
            return data.reshape(-1)

        return data.reshape(-1)

    def _build_values_mapping(self) -> dict[str, np.ndarray]:
        data = np.asarray(self._block.get("data", np.asarray([])))
        axis = np.asarray(self._block.get("axis", np.asarray([])))
        out: dict[str, np.ndarray] = {}

        if data.size == 0:
            out["CA"] = np.asarray([])
            out[self._name] = np.asarray([])
            return out

        if data.ndim == 1:
            out["CA"] = (axis.copy() if axis.size == data.size else (np.resize(axis, data.size) if axis.size > 0 else np.arange(data.size)))
            out[self._name] = data.reshape(-1)
            return out

        if data.ndim == 2:
            if axis.size == data.shape[1]:
                n_cycles = data.shape[0]
                out["CA"] = np.tile(axis, n_cycles)
                out[self._name] = data.reshape(-1)
                return out

            if axis.size == data.shape[0]:
                n_blocks = data.shape[1]
                out["CA"] = np.repeat(axis, n_blocks)
                out[self._name] = data.T.reshape(-1)
                return out

            total = data.size
            out["CA"] = np.resize(axis, total) if axis.size > 0 else np.arange(total)
            out[self._name] = data.reshape(-1)
            return out

        if data.ndim >= 3:
            axis_dim = None
            for i, s in enumerate(data.shape):
                if s == axis.size and axis.size > 0:
                    axis_dim = i
                    break

            if axis_dim is not None:
                d2 = np.moveaxis(data, axis_dim, -1)
                leading = d2.shape[:-1]
                total = int(np.prod(leading) * d2.shape[-1])
                out["CA"] = np.tile(axis, int(total // axis.size))

                if leading and leading[0] > 1:
                    reshaped = (d2.reshape(leading[0], -1, d2.shape[-1]) if len(leading) >= 2 else d2.reshape(leading[0], d2.shape[-1]))

                    comp_names = None
                    for candidate in ("channel_names", "channels", "names", "components", "subchannels"):
                        if candidate in self._block and isinstance(self._block[candidate], (list, tuple)):
                            comp_names = list(self._block[candidate])
                            break

                    if comp_names is None or len(comp_names) != reshaped.shape[0]:
                        comp_names = [f"{self._name}_{i+1}" for i in range(reshaped.shape[0])]
                    for i, cname in enumerate(comp_names):
                        out[cname] = reshaped[i].reshape(-1)
                    return out

                out[self._name] = d2.reshape(-1)
                return out

        total = data.size
        out["CA"] = np.resize(axis, total) if axis.size > 0 else np.arange(total)
        out[self._name] = data.reshape(-1)
        return out

    def __len__(self) -> int:
        return int(self._flatten_primary().size)

    def __iter__(self):
        return iter(self._flatten_primary())

    def __repr__(self) -> str:
        try:
            gen = self["GENERAL"]
        except Exception:
            gen = {}
        try:
            vals = self["VALUES"]
        except Exception:
            vals = {}
        return "{'GENERAL': " + repr(gen) + ", 'VALUES': " + repr(vals) + "}"

    def __str__(self) -> str:
        return self.__repr__()
