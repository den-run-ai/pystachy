# Item access overridden and calling the base, as collections.OrderedDict, reportlab's CIDict and
# list subclasses do: super().__setitem__(k, v), dict.__getitem__(self, k), super().__contains__
# and list.__setitem__(self, i, v) reach the builtin's own operation, while o[k], k in o and
# del o[k] call the class's methods; update() stores as dict does, past __setitem__.

class OrderedDict(dict[str, int]):
    def __init__(self) -> None:
        super().__init__()
        self._order: list[str] = []

    def __setitem__(self, key: str, value: int) -> None:
        if key not in self:
            self._order.append(key)
        super().__setitem__(key, value)

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        self._order.remove(key)

    def move_to_end(self, key: str) -> None:
        self._order.remove(key)
        self._order.append(key)

    def ordered(self) -> list[tuple[str, int]]:
        return [(k, self[k]) for k in self._order]


class CIDict(dict[str, int]):
    def __setitem__(self, k: str, v: int) -> None:
        dict.__setitem__(self, k.lower(), v)

    def __getitem__(self, k: str) -> int:
        return dict.__getitem__(self, k.lower())

    def __contains__(self, k: str) -> bool:
        return super().__contains__(k.lower())

    def __delitem__(self, k: str) -> None:
        dict.__delitem__(self, k.lower())

    def get(self, k: str, dv: int = -1) -> int:
        try:
            return self[k]
        except KeyError:
            return dv


o = OrderedDict()
o["b"] = 2
o["a"] = 1
o["c"] = 3
o["a"] = 10
o.move_to_end("b")
del o["c"]
print(o.ordered(), o, len(o), "c" in o, o._order)
o.update({"z": 26})
print(o.ordered(), o, o._order)
d = CIDict()
d["Content-Type"] = 1
d["ACCEPT"] = 2
print(d, d["content-type"], "accept" in d, "Accept" in d, d.get("X-Missing"), d.get("ACCEPT"))
del d["CONTENT-type"]
print(d, len(d), "content-type" in d)
try:
    print(d["nope"])
except KeyError as e:
    print("KeyError", e)


class Stack(list[int]):
    def __getitem__(self, i: int) -> int:
        return super().__getitem__(i) * 10

    def __setitem__(self, i: int, v: int) -> None:
        list.__setitem__(self, i, v + 1)

    def __contains__(self, x: int) -> bool:
        return list.__contains__(self, x // 10)


s = Stack([1, 2, 3])
s[0] = 5
print(s[0], s[2], s, 20 in s, 2 in s, list(s))
