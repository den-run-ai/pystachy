# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.
# pystachy: dynamic-any
# Pystachy port: CPython 3.13.16's Lib/tomllib/_types.py, with the comment above, so that
# ParseFloat's Any is a dynamic value, as in the modules that use it (docs/dynamic-any.md)

from typing import Any, Callable, Tuple

# Type annotations
ParseFloat = Callable[[str], Any]
Key = Tuple[str, ...]
Pos = int
