# pystachy: dynamic-any
import statistics
from typing import Any

xs: list[Any] = [1, 2.5, 3]
print(statistics.fmean(xs), statistics.median(xs))
