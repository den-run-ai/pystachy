class Mapping(dict[str, int]):
    pass


seen = []


class Probe:
    def __eq__(self, other):
        if other is None:
            return False
        seen.append(other)
        return isinstance(other, Mapping)


m = Mapping({"a": 1})
print(Probe() == m)
seen.append({"b": 2})
print(seen, seen == [{"a": 1}, {"b": 2}])
for row in seen:
    print(type(row).__name__, list(row), row.get("a", 0))
    row["c"] = 3
    row["c"] += 1
    print(row["c"], row.setdefault("d", 5))
    del row["c"]
print(seen, seen[0] is m)
try:
    print(seen < [{"a": 2}, {"b": 2}])
except TypeError as e:
    print(str(e))
