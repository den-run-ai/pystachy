# isinstance() of a value of object (and of a protocol's) with complex and range, which narrows it
# to a complex number's or a range's operations, as the other builtin types' tests narrow it
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class A:
    def name(self) -> str:
        return "a"


def describe(x: object) -> str:
    if isinstance(x, complex):
        return f"complex {x.real} {x.imag} {abs(x)} {x * 2} {x == complex(1, 2)}"
    if isinstance(x, range):
        return f"range {len(x)} {x.start} {x.stop} {x.step} {list(x)} {x[0] if len(x) > 0 else -1} {3 in x}"
    return f"other {isinstance(x, (complex, range))}"


def main() -> None:
    values: list[object] = [complex(1, 2), range(1, 7, 2), range(0), 1, 2.5, True, "s", None, [1], A()]
    for v in values:
        print(describe(v), isinstance(v, complex), isinstance(v, range))
    n: Named = A()
    print(isinstance(n, range), isinstance(n, complex))


main()
