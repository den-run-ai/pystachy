# Caught container misses construct an exception and take the ordinary landing
# continuation. Pin dictfuse's entry form, list bounds loads, callback-capable
# keys, and the unchanged calls outside a local try. Multiple lookups and joins
# also exercise phi predecessor repair after both lookup and invoke splitting.


def dict_read(d: dict[str, int], k: str) -> int:
    try:
        return d[k]
    except KeyError:
        return -1


def dict_increment(d: dict[str, int], k: str) -> None:
    try:
        d[k] += 1
    except KeyError:
        d[k] = 1


def list_read(xs: list[str], i: int) -> str:
    try:
        return xs[i]
    except IndexError:
        return "missing"


def joined(d: dict[str, int], xs: list[int], a: str, b: str, i: int, choose: bool) -> int:
    try:
        value = d[a] + d[b] if choose else d[b] + d[a]
        return value + xs[i]
    except (KeyError, IndexError):
        return -1


class Key:
    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        if self.value < 0:
            raise ValueError("hash failed")
        return self.value

    def __eq__(self, other: "Key") -> bool:
        return self.value == other.value

    def __repr__(self) -> str:
        if self.value == 3:
            raise RuntimeError("repr failed")
        return "Key()"


def object_read(d: dict[Key, int], k: Key) -> int:
    try:
        return d[k]
    except (KeyError, ValueError, RuntimeError):
        return -1


def dict_unhandled(d: dict[str, int], k: str) -> int:
    return d[k]


def list_unhandled(xs: list[str], i: int) -> str:
    return xs[i]


d = {"a": 1, "b": 2}
dict_increment(d, "a")
print(dict_read(d, "a"), list_read(["yes"], 0))
print(joined(d, [3], "a", "b", 0, True))
print(object_read({Key(1): 2}, Key(1)))
print(dict_unhandled(d, "a"), list_unhandled(["yes"], 0))
