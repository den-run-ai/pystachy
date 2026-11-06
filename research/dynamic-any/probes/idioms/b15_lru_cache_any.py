# pystachy: dynamic-any
# functools.lru_cache on a function of an Any argument (#620)
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=None)
def describe(x: Any) -> str:
    return type(x).__name__ + ":" + repr(x)


print(describe(1), describe("a"), describe(1), describe(2.5))
print(describe.cache_info().hits)
