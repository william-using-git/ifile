from pathlib import Path
from typing import Any, Literal, Mapping

class GeneralMeta:
    channel: str
    units: str
    description: str
    base: str
    record_count: int
    range: str
    test: str | None

class ValuesView(Mapping[str, Any]): ...

class ChannelView:
    @property
    def general(self) -> GeneralMeta: ...

    @property
    def values(self) -> ValuesView: ...

    def __getitem__(self, key: str) -> Any: ...
    def __len__(self) -> int: ...
    def __iter__(self): ...

class AxisView(Mapping[str, ChannelView]):
    def __getitem__(self, key: str) -> ChannelView: ...
    def __iter__(self): ...
    def __len__(self) -> int: ...

class ParameterValuesView(Mapping[str, Any]): ...

class ParameterView:
    @property
    def general(self) -> GeneralMeta: ...
    
    @property
    def values(self) -> ParameterValuesView: ...

    def __getitem__(self, key: str) -> Any: ...

class ParameterIndex(Mapping[str, ParameterView]):
    def __getitem__(self, key: str) -> ParameterView: ...
    def __iter__(self): ...
    def __len__(self) -> int: ...

class IFile:
    """
    High-level Python interface to an AVL IFILE via catool and MATLAB output.

    This class wraps the full lifecycle of reading an AVL IFILE:
      1) Running catool to convert the IFILE to a MATLAB (.mat) file.
      2) Loading and simplifying the MAT structure into a Python dictionary and a class object.
      3) Normalizing and enriching the data model (engine metadata, parameters,
         timestamp handling, and optional AVL-style offset corrections).
      4) Providing convenient, consistent access views for channels and parameters.

    Channels
    ---------------
    - ``ifile.ca``     -> crank-angle-based channels
    - ``ifile["CA"]``  -> crank-angle-based channels via mapping interface

    - ``ifile.cy``     -> cycle-based channels
    - ``ifile["CY"]``  -> cycle-based channels

    Each channel can then be queried for:
      - ``["GENERAL"]`` metadata (units, description, range, etc.)
      - ``["VALUES"]``  flattened numeric data aligned with the channel axis

    Example:
        pzyl = ifile["CA"]["P_ZYL1"]
        meta = pzyl["GENERAL"]
        data = pzyl["VALUES"]
        unit = ifile.ca['PSAUG'].general.units

    Parameters
    -----------
    - ``ifile.par`` -> parameters
    - ``ifile["PAR"]`` -> parameters via mapping interface

    Parameters behave like channels and support the same ``GENERAL`` /
    ``VALUES`` interface, even for scalar values.

    Example:
        eps = ifile["PAR"]["EPSILON"]["VALUES"]
        date = ifile.parameters['DATE'].values['DATE']

    Engine metadata
    ---------------
    Engine data parsed from the MAT file are available both as:

    - ``ifile.engine``     -> raw engine dictionary
    - ``ifile["ENGINE"]``  -> same object via mapping interface

    Additionally, selected engine properties are injected as parameters
    (e.g., ENGINE, BORE, STROKE, CONROD, EPSILON, NRSTROKE, PINOFF).

    Timestamps
    ----------
    Measurement time is extracted from the MAT ``header`` block and added as parameters:
      - ``DATE``      (numeric yyyymmddhhmmss form)
      - ``TIMESTAMP`` (ISO-8601 string)
    
    date = ifile["PAR"]["DATE"]["VALUES"]

    Offset correction
    ------------------
    If ``avl_correction=True`` (default), selected pressure channels are modified using reference channels to remove
    cycle-wise offsets, like in AVL Concerto™. If ``avl_correction=False``, those channels are offset corrected from catool.

    Construction parameters
    -----------------------
    Parameters
    ----------
    path : Path
        Path to the AVL IFILE (or zipped IFILE).
    log : {"INFO","DEBUG","WARNING"}
        Logging level used for both this wrapper and catool.
    avl_correction : bool, default=True
        Whether to apply Python-side AVL-style offset correction, or to use catool-style offset correction.
    keep_temp_files : bool, default=False
        If True, preserves intermediate catool working directories.
    """
    path: Path
    log: Literal['INFO', 'DEBUG', 'WARNING'] = "INFO"
    avl_correction: bool = True
    keep_temp_files: bool = False

    @property
    def engine(self) -> dict[str, Any]:
        """
        Return engine data as a dict.
        """
        ...

    @property
    def parameters(self) -> ParameterIndex:
        """
        Return all parameters as a raw name -> ParameterIndex mapping.
        """
        ...

    @property
    def ca(self) -> dict[str, ChannelView]:
        """
        Return all crank-angle channels as a name -> ChannelView mapping.
        """
        ...

    @property
    def cy(self) -> dict[str, ChannelView]:
        """
        Return all cycle-based channels as a name -> ChannelView mapping.
        """
        ...

    @property
    def correction_pairs(self) -> dict[str, str]: ...

    def __getitem__(self, key: str) -> AxisView | ParameterIndex | dict[str, Any]: ...

    def set_correction_pairs(self, pairs: dict[str, str]) -> None:
        """
        Explicitly override the channel pairs used for AVL-style offset correction.
        Has no effect on data when avl_correction = False.

        Parameters
        ----------
        pairs : dict[str, str]
            Mapping of measured channel → reference channel, e.g.::

                {"PSAUG": "SDREF", "PAUSP": "ADREF"}

            Keys must correspond to existing CA-based channels in this IFILE.
            Values must correspond to valid reference channels present in the
            same file.

        Behavior
        --------
        - Replaces any automatically detected correction pairs.
        - Does **not** retroactively re-apply corrections. It only updates
          ``ifile.correction_pairs`` for inspection or for use in a subsequent
          manual correction step.
        - To re-run corrections after calling this method, the user must call
          ``apply_offset_correction`` explicitly.

        Notes
        -----
        This method is advanced and intended for:
        - files with non-standard channel naming,
        - testing alternative reference choices, or
        - reproducing legacy processing workflows.
        """
        ...

    def reapply_corrections(self) -> None:
        """
        Explicitly reapply overwritten channel pairs used for AVL-style offset correction.
        Has no effect on data when avl_correction = False.

        Behavior
        --------
        - Retroactively re-apply corrections explicitly. The user must call
          ``set_correction_pairs`` explicitly before, to have an effect.

        Notes
        -----
        This method is advanced and intended for:
        - files with non-standard channel naming,
        - testing alternative reference choices, or
        - reproducing legacy processing workflows.
        """
        ...
