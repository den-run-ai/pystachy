# pystachy: dynamic-any
# pystachy: python-int
from typing import Any

value = 2 ** 70
query: Any = value
missing: Any = value + 1
entries: dict[int, int] = {value: value + 2, 1: 7, -2 ** 63: 9}
elements: set[int] = {value, 1, -2 ** 63}
print(entries[query], query in entries, query in elements)
print(entries.get(query), entries.get(missing), entries.get(missing, value))
queries: list[Any] = [query, float(value), True, -2 ** 63, missing, 1.5, None, "missing", float("inf"), float("nan")]
for key in queries:
    print(type(key).__name__, key in entries, key not in elements, entries.get(key, -1))
print(entries.setdefault(query, 5), entries.setdefault(missing, value + 3))
print(entries.pop(query), query in entries, entries.pop(query, None))
entries[query] = query
entries[query] += 1
print(entries[query], entries.pop(missing, value), sorted(entries))
del entries[query]
for key in [query, True]:
    try:
        print(entries[key])
    except KeyError as error:
        print("missing", str(error))
elements.discard(missing)
elements.remove(query)
elements.add(query)
print(sorted(elements), query in elements)
elements.remove(queries[1])
print(sorted(elements))
try:
    elements.remove(query)
except KeyError as error:
    print("missing element", str(error))
unhashable: Any = []
try:
    print(unhashable in entries)
except TypeError:
    print("unhashable dict query")
try:
    print(unhashable in elements)
except TypeError:
    print("unhashable set query")
words: dict[int, str] = {value: "wide"}
print(words[query], words.get(query), words.get(missing), words.get(missing, "fallback"))
print(words.pop(query, None), words.pop(query, None))
words.setdefault(query, "returned")
print(words[query], words.pop(query))
frozen: frozenset[int] = frozenset([value, 1])
print(query in frozen, missing in frozen, queries[1] in frozen)
