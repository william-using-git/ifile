import logging
import numpy as np
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, PrivateAttr
from ifile_reader.core.corrections.offset import apply_offset_correction
from ifile_reader.core.infrastructure.ifile_reader import IFileReader
from ifile_reader.core.domain.axis import AxisView
from ifile_reader.core.domain.parameter import ParameterIndex

logger = logging.getLogger(__name__)


class IFile(BaseModel):
    path: Path
    log: Literal['INFO', 'DEBUG', 'WARNING'] = "INFO"
    avl_correction: bool = True
    keep_temp_files: bool = False

    _raw: dict[str, Any] = PrivateAttr(default_factory=dict)
    _reader: Any = PrivateAttr(default=None)

    @property
    def engine(self) -> dict:
        return self._raw.get("engine", {})

    @property
    def parameters(self) -> ParameterIndex:
        return ParameterIndex(self)

    @property
    def ca(self):
        return {ch: self["CA"][ch] for ch in self["CA"]}

    @property
    def cy(self):
        return {ch: self["CY"][ch] for ch in self["CY"]}
    
    @property
    def correction_pairs(self) -> dict[str, str]:
        return self._raw.get("_correction_pairs", {})


    def __init__(self, *args: Any, **kwargs: Any) -> None:
        positional_fields = ("path", "log", "avl_correction", "keep_temp_files")
        for i, val in enumerate(args):
            if i >= len(positional_fields):
                break
            key = positional_fields[i]
            if key not in kwargs:
                kwargs[key] = val

        super().__init__(**kwargs)


    def model_post_init(self, __context: Any) -> None:
        log_level = getattr(logging, self.log, logging.INFO)
        logger.setLevel(log_level)
        root = logging.getLogger()
        if not root.handlers:
            logging.basicConfig(level=log_level)
        else:
            try:
                if root.level > log_level or root.level == 0:
                    root.setLevel(log_level)
            except Exception:
                logger.debug("Could not set root logger level", exc_info=True)

        reader = IFileReader(keep_temp_files=self.keep_temp_files)
        self._reader = reader
        
        offset_correction = not self.avl_correction
        self._raw = reader.load_ifile(self.path, offset_correction=offset_correction, simplify=True, convert_arrays=False)
        self._raw["_test"] = str(self.path)

        eng: dict = self._raw.get("engine", {})
        eng_name = eng.get("name")
        bore = eng.get("bore")
        stroke = eng.get("stroke")
        conrod_len = eng.get("conrod_length")
        compression = eng.get("compression_ratio")
        num_stroke = eng.get("number_of_strokes")
        pin_off = eng.get("pin_offset")

        self._raw.setdefault("parameters", {})

        if eng_name is not None:
            self._raw["parameters"]["ENGINE"] = {
                "value": eng_name,
                "unit": "",
                "description": "engine name"
            }
        if bore is not None:
            self._raw["parameters"]["BORE"] = {
                "value": bore,
                "unit": "",
                "description": "bore diameter"
            }
        if stroke is not None:
            self._raw["parameters"]["STROKE"] = {
                "value": stroke,
                "unit": "",
                "description": "stroke length"
            }
        if conrod_len is not None:
            self._raw["parameters"]["CONROD"] = {
                "value": conrod_len,
                "unit": "",
                "description": "conrod length"
            }
        if compression is not None:
            self._raw["parameters"]["EPSILON"] = {
                "value": compression,
                "unit": "",
                "description": "compression"
            }
        if num_stroke is not None:
            self._raw["parameters"]["NRSTROKE"] = {
                "value": num_stroke,
                "unit": "",
                "description": "number of strokes"
            }
        if pin_off is not None:
            self._raw["parameters"]["PINOFF"] = {
                "value": pin_off,
                "unit": "",
                "description": "pinoff"
            }

        header: dict = self._raw.get("header", {})
        date_str = header.get("date")

        if isinstance(date_str, str) and len(date_str) >= 14:
            ts_iso = (
                f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]} "
                f"{date_str[8:10]}:{date_str[10:12]}:{date_str[12:14]}"
            )
            self._raw["parameters"]["DATE"] = {
                "value": date_str,
                "unit": "",
                "description": "date of measurement",
            }
            self._raw["parameters"]["TIMESTAMP"] = {
                "values": np.array([ts_iso], dtype=object),
                "unit": "",
                "description": "time stamp",
            }

        if self.avl_correction:
            pairs = self._find_reference_channels()
            self._raw["_correction_pairs"] = pairs
            for meas, ref in pairs.items():
                logger.debug(f"Applying offset correction: {meas} -> {ref}")
                apply_offset_correction(self._raw, meas, ref)


    def __getitem__(self, key: str):
        ku = key.upper()
        if ku == "ENGINE":
            return self.engine
        if ku in ("CA", "CY"):
            return AxisView(self._raw, ku)
        if ku == "PAR":
            return ParameterIndex(self)
        raise KeyError(key)


    def _find_reference_channels(self) -> dict[str, str]:
        ca_channels = set(self["CA"])
        pairs = {}
        if "SDREF" in ca_channels:
            for ch in ca_channels:
                if ch.endswith("SAUG"):
                    pairs[ch] = "SDREF"

        if "ADREF" in ca_channels:
            for ch in ca_channels:
                if ch.endswith("AUSP"):
                    pairs[ch] = "ADREF"

        return pairs
    

    def set_correction_pairs(self, pairs: dict[str, str]) -> None:
        self._raw["_correction_pairs"] = dict(pairs)


    def reapply_corrections(self):
        for meas, ref in self.correction_pairs.items():
            apply_offset_correction(self._raw, meas, ref)
