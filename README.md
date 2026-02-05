# ifile

A compact Python wrapper around [`catool`](https://catool.org/) to extract AVL's industry-standard IFile format into Python-native structures (ifile → MAT → dict and class object). Designed to be lightweight and easy to use.

> This repository includes `catool` (Copyright (C) Xarin Limited 2000-2025), which is used under the GNU General Public License. Therefore, this project is also subject to the GNU General Public License. \
AVL and I-File are likely trademarks of AVL Graz GmbH. \
MATLAB is a trademark of The MathWorks, Inc.
---

## Features

- Run `catool` to convert AVL IFiles to MATLAB `.mat`.
- Simplified MAT → Python conversion preserving arrays, strings and struct fields.
- Option to preserve run artifacts (`run.ccf`, `output.mat`) for debugging via `keep_temp_files`.
- Fine-grained control on whether to let `catool` perform internal offset corrections or perform corrections  producing the same values as AVL Concerto™ (see `offset_correction` / `avl_correction` behaviour in the higher-level API).
- Views for crank angle- and cycle based channels, parameters, and engine data.

---

## Installation

pip users:
```bash
pip install ifile-reader
```
Poetry users:
```bash
poetry add ifile-reader
```
Import:
```python
from ifile_reader import IFile
```
## Usage

Simply creating the ifile object (the ifile is read inside the constructor):

```python
ifile = IFile(<ifile_path>)
```

Then it can be used like a dict (with the same interface as AVL Concerto™):
```python
ca = ifile['CA']
pars = ifile['PAR']
cy = ifile['CY']

epsilon = ifile['PAR']['EPSILON']
date = ifile["PAR"]["DATE"]["VALUES"]

p3 = ifile['PAR']['P3']['VALUES']['P3']

psaug_overview = ifile['CA']['PSAUG']['GENERAL']
```

Or using class members
```python
ca = ifile.ca
pars = ifile.parameters
cy = ifile.cy
```

It's also possible to control via static members (with autocompletion):
```python
psaug = ifile['CA']['PSAUG'].values
unit = ifile.ca['PSAUG'].general.units
```

Engine data are also available both as:

```python
ifile.engine     # raw engine dictionary
ifile["ENGINE"]  # same object via mapping interface
```

Additionally, selected engine properties are injected as parameters
(e.g., ENGINE, BORE, STROKE, CONROD, EPSILON, NRSTROKE, PINOFF).


Arguments for IFile:
    
    path : Path
        # Path to the AVL IFILE (or zipped IFILE).

    log : {"INFO","DEBUG","WARNING"}
        # Logging level used for both this wrapper and catool.

    avl_correction : bool, default=True
        # Whether to apply Python-side AVL-style offset correction, or to use catool-style offset correction.
        
    keep_temp_files : bool, default=False
        # If True, preserves intermediate catool working directories.


### Offset correction control

By default, `IFile` applies AVL-style offset correction in Python (`avl_correction=True`).
Correction channel pairs are detected heuristically from the available crank-angle channels (e.g. `PSAUG → SDREF`, `PAUSP → ADREF`) and applied automatically during construction.

**General interaction with `avl_correction`:**

- avl_correction=True (default)

    - Corrections are detected and applied automatically at load time producing values like AVL Concerto™.

    - One may still override them with `set_correction_pairs()` and re-run via `reapply_corrections()`.

- avl_correction=False

    - Catool performs its internal offset correction.

    - `set_correction_pairs()` and `reapply_corrections()` have no effect unless the file is reloaded with `avl_correction=True`.


For `avl_correction`, it can be inspected which pairs were detected:
```python
ifile.correction_pairs
# e.g. {'PSAUG': 'SDREF', 'PAUSP': 'ADREF'}
```

**Overriding correction pairs**

For files with non-standard channel names, or when experimenting with alternative references, the automatically detected pairs can be overwritten:
```python
ifile.set_correction_pairs({
    "P_1": "SDREF",
    "P_2": "SDREF",
})
```

This only updates the mapping used by `IFile`. It does not immediately change the data.

**Re-applying corrections**

After setting new pairs, the correction can be explicitly re-run:
```python
ifile.reapply_corrections()
```

This will call `apply_offset_correction` for each pair in `ifile.correction_pairs`.

