# Names bound only in code that CPython never runs here (tests/optional_partial.py).
import sys
from typing import TYPE_CHECKING

if sys.platform == "win32":
    val = 1
if TYPE_CHECKING:
    tc = 2
if __name__ == "__main__":
    mn = 3
here = 4
