# pystachy: dynamic-any
from typing import Any

def keys_of(table: dict[str, Any]) -> list[str]:
    return list(table)


doc: Any = {"a": 1}
print(keys_of(doc))
