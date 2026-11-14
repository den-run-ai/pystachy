# pystachy: dynamic-any
import textwrap
from typing import Any

s: Any = "the quick brown fox jumps over the lazy dog"
if isinstance(s, str):
    print(textwrap.wrap(s, 12))
