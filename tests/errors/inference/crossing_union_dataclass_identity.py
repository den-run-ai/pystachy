# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row dataclass: without `is`
import dataclasses


@dataclasses.dataclass
class D:
    a: int
    b: str

    def describe(self) -> str:
        return "D" + str(self.a)


def pick(v: D | int) -> D | int:
    return v


def main() -> None:
    x: D | int = pick(D(1, 'b'))
    print(x is x, x is not x)


main()
