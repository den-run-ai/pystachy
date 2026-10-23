# pystachy: dynamic-any
from typing import Any
seen: list[Any] = []

class Key:
    def __hash__(self) -> int:
        return 1000

    def __eq__(self, value: Any) -> bool:
        seen.append(value)
        return value == 1000


def run() -> None:
    k = int('1000')
    d: dict[int, Any] = {}
    print(k in d)
    alias: Any = d
    alias[Key()] = 'value'
    print(k in d, d[k], seen[0] is k, seen[-1] is k)
    kept: Any = k
    d.clear()
    d[k] = 'integer'
    print(k in d, d[k], kept is k)
    d.clear()
    alias[Key()] = 'again'
    print(k in d, d[k], seen[-1] is kept)

run()
