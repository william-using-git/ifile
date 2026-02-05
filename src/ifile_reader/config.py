from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class CatoolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    lib_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "lib")
    keep_temp_files: bool = False
    catool_path: Optional[Path] = None
    download_if_missing: bool = True
    subprocess_timeout: Optional[int] = 60
