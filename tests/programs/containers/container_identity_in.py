# x in t over a tuple tests each item by identity before ==, as CPython's tuple.__contains__
# does (and as a list's search does, see container_identity.py): a list, dict or tuple holding
# a NaN is in a tuple that holds it, also where it may be None, and a distinct one with the
# same items is not.
from typing import NamedTuple

calls = 0


class Probe:
    def __init__(self, value: int):
        self.value = value

    def __eq__(self, other: "Probe") -> bool:
        global calls
        calls += 1
        return self.value == other.value


leaf = [float("nan")]
mapping = {0: float("nan")}
pair = (float("nan"),)
other = [float("nan")]
print("shared", leaf in (leaf,), mapping in (mapping,), pair in (pair,))
print("not in", leaf not in (leaf,), mapping not in (mapping,), pair not in (pair,))
print("later", leaf in (other, leaf), mapping in ({0: float("nan")}, mapping), pair in ((float("nan"),), pair))
print("distinct", other in (leaf,), {0: float("nan")} in (mapping,), (float("nan"),) in (pair,))
print("distinct not in", other not in (leaf,), [float("nan")] not in (leaf, other))
print("children", [leaf] in ([leaf],), (leaf,) in ((leaf,),), {0: leaf} in ({0: leaf},))
print("mixed", leaf in (1, "a", leaf), leaf in (1, "a"))
names = {"a"}
print("set", names in (names,), {"a"} in (names,), {"b"} in (names,))


def star(*args: list[float]) -> None:
    print("star", leaf in args, other in args, leaf not in args)


star(leaf)
star(other, leaf)


class Row(NamedTuple):
    cells: list[float]
    n: int


row = Row(leaf, 1)
print("namedtuple", leaf in row, other in row, leaf not in row)

# the item that is the operand ends the search before == runs on it or on a later item
probe = (leaf, Probe(1))
print("first", probe in (probe, (leaf, Probe(1))), calls)
print("equal", (leaf, Probe(1)) in ((other, Probe(1)), probe), calls)


def optional_list(v: list[float] | None) -> None:
    print("optional list", v in (v, None), v not in (v,), v in (other,), v in (None,))


def optional_dict(v: dict[int, float] | None) -> None:
    print("optional dict", v in (v, None), v not in (v,), v in ({0: float("nan")},), v in (None,))


def optional_tuple(v: tuple[float] | None) -> None:
    print("optional tuple", v in (v, None), v not in (v,), v in ((float("nan"),),), v in (None,))


def optional_items(v: list[float] | None, w: list[float] | None) -> None:
    print("optional items", leaf in (v, w), v in (w,), None in (v, w), v not in (w, v))


optional_list(leaf)
optional_list(None)
optional_dict(mapping)
optional_dict(None)
optional_tuple(pair)
optional_tuple(None)
optional_items(leaf, other)
optional_items(None, leaf)
optional_items(other, None)
