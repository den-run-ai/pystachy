# pystachy: dynamic-any
from typing import Any

flags: dict[str, dict[Any, Any]] = {"a": {"nested": {"b": 1}}}


def find(key: list[str]) -> Any:
    cont = flags
    for k in key[:-1]:
        cont = cont[k]["nested"]
    return cont.get(key[-1])


print(find(["a", "b"]))
