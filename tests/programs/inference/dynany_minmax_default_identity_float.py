# pystachy: dynamic-any
# A float default, including an optional one, retains its object across lazy consumption.
from typing import Any

fallback = float("nan")
original: Any = fallback
generated: Any = max((float(x) for x in range(0)), default=fallback)
mapped: Any = min(map(float, range(0)), default=fallback)
empty: list[float] = []
listed: Any = max(empty, default=fallback)
print(generated is original, mapped is original, listed is original)

optional: float | None = fallback
optional_original: Any = optional
optional_result: Any = max((float(x) for x in range(0)), default=optional)
print(optional_result is optional_original)
optional = None
none_result: Any = min((float(x) for x in range(0)), default=optional)
print(none_result is None)

nonempty: Any = max((float(x) for x in range(2)), default=fallback)
print(nonempty, nonempty is original)
