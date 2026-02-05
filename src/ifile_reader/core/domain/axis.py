import numpy as np
from collections.abc import Mapping
from ifile_reader.core.domain.dependencies import _classify_axis
from ifile_reader.core.domain.channel import ChannelView


class AxisView(Mapping):
    def __init__(self, raw: dict, axis: str):
        self._raw = raw or {}
        self._axis = axis.upper()

    def _channels(self) -> dict[str, dict]:
        out = {}
        for name, block in self._raw.items():
            if not isinstance(block, dict):
                continue
            if "data" not in block or "axis" not in block:
                continue

            axis_arr = np.asarray(block.get("axis", []))
            if _classify_axis(axis_arr) == self._axis:
                out[name] = block
        return out

    def __getitem__(self, channel: str):
        chans = self._channels()
        if channel not in chans:
            raise KeyError(f"Channel '{channel}' not found in {self._axis}")
        return ChannelView(channel, chans[channel], self._raw.get("_test"))

    def __iter__(self):
        return iter(self._channels())

    def __len__(self):
        return len(self._channels())

    def __repr__(self):
        return repr(sorted(self._channels().keys(), key=str.lower))

    def __str__(self):
        return self.__repr__()
