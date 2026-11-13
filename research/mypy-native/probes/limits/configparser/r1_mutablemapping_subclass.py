from collections.abc import MutableMapping


class Proxy(MutableMapping):
    def __init__(self, d: dict[str, str]) -> None:
        self._d = d

    def __getitem__(self, key: str) -> str:
        if key not in self._d:
            raise KeyError(key)
        return self._d[key]

    def __setitem__(self, key: str, value: str) -> None:
        self._d[key] = value

    def __delitem__(self, key: str) -> None:
        del self._d[key]

    def __iter__(self):
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)


p = Proxy({"a": "1"})
p["b"] = "2"
print(p["a"], len(p), list(p), "a" in p, "z" in p)
print(list(p.keys()), list(p.values()), list(p.items()))
print(p.get("a"), p.get("z"), p.get("z", "dflt"))
del p["a"]
print(list(p), p.pop("b"), len(p))
p.update({"x": "y"})
print(p.setdefault("q", "r"), dict(p))
for k, v in p.items():
    print(k, v)
