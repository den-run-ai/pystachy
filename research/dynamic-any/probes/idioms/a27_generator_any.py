# pystachy: dynamic-any
# a generator yielding Any values from mixed records
from typing import Any, Iterator


def fields(rows: list[Any], key: str) -> Iterator[Any]:
    for r in rows:
        if key in r:
            yield r[key]


rows: list[Any] = [{"a": 1}, {"a": "x"}, {"b": 2}, {"a": [3]}]
print(list(fields(rows, "a")))
