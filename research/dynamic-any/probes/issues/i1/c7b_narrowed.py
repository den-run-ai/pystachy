# pystachy: dynamic-any
from typing import Any


def keys_of(table: dict[str, Any]) -> list[str]:
    return list(table)


def run(doc: Any) -> None:
    if isinstance(doc, dict):
        print(keys_of(doc))


run({"a": 1})
