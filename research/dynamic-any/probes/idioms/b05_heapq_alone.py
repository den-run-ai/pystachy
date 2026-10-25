# pystachy: dynamic-any
# heapq with Any items alone
import heapq
from typing import Any

xs: list[Any] = [5, 1.5, 3, 2]
heapq.heapify(xs)
print([heapq.heappop(xs) for _ in range(4)])
