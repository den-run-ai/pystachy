# defaults of a parameter, given by a module that does not opt in to dynamic Any: numbers, strs,
# bools, None, tuples, values of a union type, list and dict displays, a list of ints, objects,
# enum members and functions keep their values, types and identity
import enum
import inspect
import sys

KO = inspect.Parameter.KEYWORD_ONLY


class Color(enum.Enum):
    RED = 1


class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return f"Point({self.x})"


def scale(v: float) -> float:
    return v * 2


def literal(i: int) -> int | float | str | bool | None:
    if i == 0:
        return None
    if i == 1:
        return i + 6
    if i == 2:
        return 1.5 * i
    if i == 3:
        return "s" * i
    return i > 3


def make(n: int, s: str, f: float, b: bool, t: tuple[int, str, None]) -> list[inspect.Parameter]:
    out = []
    out.append(inspect.Parameter("i", KO, default=n))
    out.append(inspect.Parameter("s", KO, default=s))
    out.append(inspect.Parameter("f", KO, default=f))
    out.append(inspect.Parameter("b", KO, default=b))
    out.append(inspect.Parameter("n", KO, default=None))
    out.append(inspect.Parameter("t", KO, default=t))
    out.append(inspect.Parameter("big", KO, default=n - 9223372036854775807))
    out.append(inspect.Parameter("e", KO))
    return out


n = len(sys.argv) - 3  # 0, which only the run knows
ps = make(n + 42, "text", 2.5, True, (n + 1, "one", None))
for p in ps:
    # (the marker's type is the deviation tests/deviations/lib_inspect_empty_marker.py)
    print(p.name, p, repr(p), p.default, repr(p.default),
          "no default" if p.default is inspect.Parameter.empty else type(p.default).__name__)
print(f"f{inspect.Signature(ps)}")

for i in range(5):
    p = inspect.Parameter("u" + str(i), KO, default=literal(i + n))
    d = p.default
    if isinstance(d, bool):
        print(p, "bool", not d)
    elif isinstance(d, int):
        print(p, "int", d + 1)
    elif isinstance(d, float):
        print(p, "float", d * 2)
    elif isinstance(d, str):
        print(p, "str", d.upper())
    elif d is None:
        print(p, "None")

ints = [n + 1, n + 2]
ints.append(3)
point = Point(n + 7)
containers = [
    inspect.Parameter("l", KO, default=[1, "two", 3.0]),
    inspect.Parameter("empty", KO, default=[]),
    inspect.Parameter("d", KO, default={"a": 1, "b": None}),
    inspect.Parameter("ints", KO, default=ints),
    inspect.Parameter("o", KO, default=point),
    inspect.Parameter("c", KO, default=Color.RED),
    inspect.Parameter("fn", KO, default=scale),
]
print(inspect.Signature(containers[:6]))
print(containers[3].default is ints, containers[4].default is point, containers[4].default is Point(7),
      containers[5].default is Color.RED, containers[6].default is scale, containers[6].default is literal)
ints.append(4)
point.x = 8
print(containers[3], containers[4], len(containers[3].default), containers[0].default[1], containers[2].default["a"])
