import os
import platform
import sys
import tempfile
import zipfile
import urllib.request
import subprocess
import shutil
import logging
import locale
from pathlib import Path
from typing import Optional
from ifile_reader.config import CatoolConfig

logger = logging.getLogger(__name__)


class CatoolRunner:
    def __init__(self, config: Optional[CatoolConfig] = None):
        self.config = config or CatoolConfig()

    @staticmethod
    def _is_64bit() -> bool:
        return sys.maxsize > 2**31

    @staticmethod
    def _exe_name() -> str:
        return "catool.exe" if platform.system() == "Windows" else "catool"

    @classmethod
    def _download_url(cls) -> str:
        is64 = cls._is_64bit()
        sysname = platform.system()
        if sysname == "Windows":
            return "https://catool.org/files/catool-latest-win64.zip" if is64 else "https://catool.org/files/catool-latest-win32.zip"
        if sysname == "Darwin":
            return "https://catool.org/files/catool-latest-macos.zip"
        if sysname == "Linux":
            return "https://catool.org/files/catool-latest-linux64.zip" if is64 else "https://catool.org/files/catool-latest-linux32.zip"
        raise RuntimeError(f"Unsupported platform: {sysname}")


    def ensure_executable(self) -> Path:
        if self.config.catool_path:
            p = Path(self.config.catool_path)
            if p.exists() and p.is_file():
                return p
            logger.warning(f"Configured catool_path does not exist: {p}")

        sys_path = shutil.which(self._exe_name())
        if sys_path:
            logger.debug(f"Using system catool at {sys_path}")
            return Path(sys_path)

        lib_dir = self.config.lib_dir
        lib_dir.mkdir(parents=True, exist_ok=True)
        exe_path = lib_dir / self._exe_name()
        if exe_path.is_file():
            logger.debug(f"Using catool installed in lib_dir: {exe_path}")
            return exe_path

        if not self.config.download_if_missing:
            raise FileNotFoundError("catool executable not found and download_if_missing is False")

        url = self._download_url()
        fd, tmp_zip = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        tmp_zip_path = Path(tmp_zip)

        logger.info(f"Downloading latest catool from {url}...")
        try:
            urllib.request.urlretrieve(url, str(tmp_zip_path))
            with zipfile.ZipFile(tmp_zip_path, "r") as zf:
                zf.extractall(lib_dir)

            for f in lib_dir.rglob(self._exe_name()):
                try:
                    if platform.system() in ("Linux", "Darwin"):
                        f.chmod(0o755)
                except Exception:
                    pass
                return f

            raise RuntimeError(f"catool was not found after extraction in {lib_dir}")
        finally:
            tmp_zip_path.unlink(missing_ok=True)


    def run(self, script: Path, *, log_level: str, timeout: Optional[int]) -> None:
        exe_path = self.ensure_executable()
        env = os.environ.copy()
        try:
            enc = locale.getpreferredencoding(False) or "UTF-8"
            if platform.system() != "Windows":
                env.setdefault("LC_ALL", f"C.{enc}")
            env.setdefault("LANG", f"C.{enc}")
        except Exception:
            env.setdefault("LANG", "C.UTF-8")

        cmd = [str(exe_path), f"--debug-level={log_level}", str(script)]
        logger.debug("Running catool: %s", " ".join(cmd))

        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False, env=env)
        if proc.stdout:
            try:
                logger.debug(f"catool stdout:\n{proc.stdout.decode('utf-8', errors='ignore')}")
            except Exception:
                logger.debug("catool stdout contained undecodable bytes (suppressed)")
        if proc.stderr:
            try:
                logger.debug(f"catool stderr:\n{proc.stderr.decode('utf-8', errors='ignore')}")
            except Exception:
                logger.debug("catool stderr contained undecodable bytes (suppressed)")

        if proc.returncode != 0:
            raise RuntimeError(
                "catool did not exit successfully\n"
                f"Command: {' '.join(cmd)}\n"
                f"Return code: {proc.returncode}\n"
                f"STDOUT:\n{proc.stdout}\n"
                f"STDERR:\n{proc.stderr}\n"
            )
