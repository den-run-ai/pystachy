# error: comparing closed union values requires narrowing with isinstance() first
# crossing matrix (tools/crossing_matrix.py), column union, row enum: without `is`
import enum


class Color(enum.Enum):
    RED = 1
    BLUE = 2

    def describe(self) -> str:
        return "Color" + str(self.value)


def pick(v: Color | int) -> Color | int:
    return v


def main() -> None:
    x: Color | int = pick(Color.RED)
    print(x is x, x is not x)


main()
