# Dictionary displays need the same contextual typing without affecting key evaluation.
values: list[dict[str, int]] = [{"a": 1}, {"b": 2, "c": 3}]
empty: list[dict[str, int]] = []
print(max((x for x in values), default={}, key=len))
print(min((x for x in values), key=len, default={}))
print(max((x for x in empty), default={}, key=len))
print(min(map(lambda x: x, empty), key=len, default={}))
print(max(reversed(values), default={}, key=len))

first = min((x for x in empty), default={}, key=len)
second = min((x for x in empty), default={}, key=len)
first["fresh"] = 4
print(first, second, first is second)
