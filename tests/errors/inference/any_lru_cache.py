# error: square()'s parameter 'x' is annotated Any, which gives no type to the type variables it matches
# lru_cache types its wrapper from the function's signature, which a parameter annotated Any (left
# to each call, as an unannotated one is) does not give: annotate a concrete type
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=None)
def square(x: Any) -> int:
    return x * x


print(square(3))
