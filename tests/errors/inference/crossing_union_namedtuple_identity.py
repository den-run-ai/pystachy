# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row namedtuple: without `is`
from typing import NamedTuple


class N(NamedTuple):
    a: int
    b: str

    def describe(self) -> str:
        return "N" + str(self.a)


def pick(v: N | int) -> N | int:
    return v


def main() -> None:
    x: N | int = pick(N(1, 'b'))
    print(x is x, x is not x)


main()
