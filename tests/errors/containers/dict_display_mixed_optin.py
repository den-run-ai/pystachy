# error: expected str, got int (this dict display's values have no one type: annotate the display with a union of their types where one holds them, or add '# pystachy: dynamic-any' before the module's code
# Values that no one type holds, nor a union the compiler infers: the error names what holds
# them, an annotation or the module's dynamic Any opt-in, before the call that compiled it
from typing import Any


def load() -> dict[str, Any]:
    return {"name": "x", "n": 3, "tags": ["a", "b"]}


print(load())
