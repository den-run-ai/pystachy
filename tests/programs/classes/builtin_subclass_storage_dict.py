class Mapping(dict[str, int]):
    pass


seen = {}
alias = seen


class Probe:
    def __eq__(self, other):
        seen["first"] = other
        return isinstance(other, Mapping)


m = Mapping()
m["a"] = 1
print(Probe() == m)
alias.setdefault("second", {"b": 2})
m["c"] = 3
print(type(alias["first"]).__name__, alias["first"] is m)
print(seen)
alias["second"] = m
print(type(seen["second"]).__name__, seen["first"] is seen["second"])
