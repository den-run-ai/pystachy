# pystachy: dynamic-any
# an Any string narrowed before it enters a typed library function
import textwrap
from typing import Any

s: Any = "the quick brown fox jumps over the lazy dog"
if isinstance(s, str):
    print(textwrap.wrap(s, 12))
