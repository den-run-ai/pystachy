# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, a tuple whose item is an Any value where a typed item is declared converts item by item,
# checking the Any item's type where it unboxes it: TypeError where CPython, which does not check
# annotations, goes on (here it would print [('a', 1), (5, 2)]).
# pystachy: dynamic-any
from typing import Any

rows: list[tuple[str, Any]] = []
key: Any = "a"
rows.append((key, 1))
print(rows)
key = 5
rows.append((key, 2))
print(rows)
