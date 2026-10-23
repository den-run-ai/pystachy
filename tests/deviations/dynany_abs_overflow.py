# pystachy: dynamic-any
# The existing signed-64-bit limit applies to abs's integer result too.
import sys
from typing import Any

value: Any = -sys.maxsize - 1
try:
    print(abs(value))
except OverflowError as error:
    print(error)
