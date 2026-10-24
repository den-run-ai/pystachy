# pystachy: dynamic-any
# N ints above the small-int cache, boxed into a list[Any] (heap cost of boxes; compare ints.py)
import sys
from typing import Any

n = int(sys.argv[1])
xs: list[Any] = []
for i in range(n):
    xs.append(i + 1000)
print(len(xs), xs[-1])
