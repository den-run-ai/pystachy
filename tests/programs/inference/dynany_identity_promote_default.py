# No opt-in here: the python-int gate promotes this entry module independently.
import intidentity

value = int("10000")


def default(item: int = value) -> None:
    intidentity.keep(item)


intidentity.keep(value)
value = int("10000")
intidentity.churn()
default()
intidentity.check("definition time default")
default()
intidentity.churn()
default()
intidentity.check("repeated default")
default()
intidentity.keep(value)
intidentity.check("rebound global")


def captured_defaults():
    first = int("11000")
    second = int("12000")
    fraction = float("1.25")

    def read(a: int = first, b: int = second, c: float = fraction) -> None:
        intidentity.keep(a)
        intidentity.keep(first)
        intidentity.check("first captured default")
        intidentity.keep(b)
        intidentity.keep(second)
        intidentity.check("second captured default")
        intidentity.keep(c)
        intidentity.keep(fraction)
        intidentity.check("float captured default")

    return read


reader = captured_defaults()
intidentity.churn()
reader()
reader()
