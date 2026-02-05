import logging
import shutil
import time
import zipfile
import tempfile
import numpy as np
from typing import Any
from scipy.io.matlab import mio5_params
from contextlib import nullcontext
from scipy.io import loadmat, whosmat
from pathlib import Path
from typing import Any, Optional, Union
from ifile_reader.core.infrastructure.catool import CatoolRunner

logger = logging.getLogger(__name__)


class IFileReader:
    def __init__(self, runner: Optional[CatoolRunner] = None, keep_temp_files: bool = False):
        self.runner = runner or CatoolRunner()
        self.keep_temp_files = keep_temp_files

        self._last_mat: Optional[Path] = None
        self._last_run_script: Optional[Path] = None
        self._last_preserved_dir: Optional[Path] = None

    def load_ifile(
        self,
        filename: Union[str, Path],
        channels: list[str] | None = None,
        offset_correction: bool = True,
        *,
        simplify: bool = True,
        convert_arrays: bool = False,
        loadmat_kwargs: Optional[dict[str, object]] = None,
    ) -> dict[str, Any]:

        if logger.isEnabledFor(logging.DEBUG):
            catool_level = "DEBUG"
        elif logger.isEnabledFor(logging.INFO):
            catool_level = "INFO"
        elif logger.isEnabledFor(logging.WARNING):
            catool_level = "WARNING"
        else:
            catool_level = "SILENT"

        filename_path = Path(filename).expanduser().resolve()
        if not filename_path.is_file():
            raise FileNotFoundError(str(filename_path))

        unzip_ctx = tempfile.TemporaryDirectory(prefix="ifile_unzip_") if zipfile.is_zipfile(filename_path) else nullcontext(None)
        with unzip_ctx as unzip_dir_raw:
            if unzip_dir_raw:
                unzip_dir = Path(unzip_dir_raw)
                with zipfile.ZipFile(filename_path, "r") as zf:
                    zf.extractall(unzip_dir)
                extracted_files = sorted(p for p in unzip_dir.rglob("*") if p.is_file())
                if not extracted_files:
                    raise RuntimeError("Archive contains no files")
                input_file = extracted_files[0]
                logger.debug(f"Zip contained files, using {input_file}")
            else:
                input_file = filename_path

            with tempfile.TemporaryDirectory(prefix="catool_run_") as run_dir_raw:
                run_dir = Path(run_dir_raw)
                script_path = run_dir.joinpath("run.ccf")
                mat_path = run_dir.joinpath("output.mat")

                script_lines = [
                    'locale ".utf8"',
                    "input-file-type AVL_IFILE",
                    "input-data ALL",
                    f'input-file "{input_file}"',
                    "load-channels all",
                    "load-file",
                ]

                if not offset_correction:
                    script_lines.append("channel all channel-offset type NONE")

                script_lines += [
                    "analyse none",
                    "run-analysis",
                    f'output-file "{mat_path}"',
                    f"output-data ALL",
                    "output-file-type MATLAB",
                    "output",
                    "",
                ]

                script_path.write_text("\n".join(script_lines), encoding="utf-8")
                self.runner.run(script_path, log_level=catool_level, timeout=self.runner.config.subprocess_timeout)

                if not mat_path.exists():
                    logger.error(f"Expected MAT file {mat_path} not found after running catool")
                    raise RuntimeError("catool did not produce a MAT file at expected path: %s" % mat_path)
                
                preserved_dir = None
                if self.keep_temp_files:
                    try:
                        lib_dir = Path(getattr(self.runner.config, "lib_dir", Path.cwd()))
                        preserved = lib_dir.joinpath(f"catool_run_{int(time.time())}")
                        preserved.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(run_dir, preserved, dirs_exist_ok=True)
                        preserved_dir = preserved
                        logger.info(f"Preserved run directory at {preserved_dir}")
                    except Exception:
                        logger.exception("Failed to preserve run directory. Continuing without preserved copy")

                self._last_mat = mat_path
                self._last_run_script = script_path
                self._last_preserved_dir = preserved_dir

                vars_info = whosmat(str(mat_path))
                available_vars = {name for name, *_ in vars_info}
                logger.debug("MAT variables: %s", ", ".join(sorted(available_vars)))

                if channels:
                    requested = [c for c in channels if c in available_vars]
                    missing = [c for c in channels if c not in available_vars]
                    if missing:
                        logger.warning(f"Requested channels not in MAT: {missing}")
                    if len(requested) == 0:
                        requested = None
                else:
                    requested = None

                kwargs = {"squeeze_me": True, "struct_as_record": False}
                if loadmat_kwargs:
                    kwargs.update(loadmat_kwargs)

                raw = loadmat(str(mat_path), variable_names=requested, **kwargs) if requested else loadmat(str(mat_path), **kwargs)
                return self.simplify_loadmat_dict(raw, convert_arrays) if simplify else raw


    def simplify_loadmat_dict(self, mat_dict: dict[str, Any], convert_arrays: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in mat_dict.items():
            if k in ("__header__", "__version__", "__globals__"):
                out[k] = v
                continue
            out[k] = self._convert_matobj(v, convert_arrays)
        return out


    def _is_matstruct(self, obj: object) -> bool:
        try:
            return isinstance(obj, mio5_params.mat_struct)
        except Exception:
            return False


    def _decode_bytes(self, x: object) -> object:
        if isinstance(x, (bytes, bytearray)):
            try:
                return x.decode("utf-8", errors="ignore")
            except Exception:
                return x
        return x


    def _ndarray_to_py(self, x: np.ndarray, convert_arrays: bool) -> object:
        if x.dtype == object:
            py = x.tolist()
            return self._convert_matobj(py, convert_arrays)
        if convert_arrays:
            return self._convert_matobj(x.tolist(), convert_arrays)
        if x.size == 1:
            try:
                return x.item()
            except Exception:
                return x
        return x


    def _convert_matobj(self, matobj: object, convert_arrays: bool = False) -> object:
        if self._is_matstruct(matobj):
            result: dict = {}
            for fn in getattr(matobj, "_fieldnames", []):
                result[fn] = self._convert_matobj(getattr(matobj, fn), convert_arrays)
            return result
        if isinstance(matobj, list):
            return [self._convert_matobj(elem, convert_arrays) for elem in matobj]
        if isinstance(matobj, np.ndarray):
            return self._ndarray_to_py(matobj, convert_arrays)
        if isinstance(matobj, (np.generic,)):
            try:
                return matobj.item()
            except Exception:
                return matobj
        if isinstance(matobj, (bytes, bytearray)):
            return self._decode_bytes(matobj)
        return matobj