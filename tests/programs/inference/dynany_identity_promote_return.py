# No opt-in here: the python-int gate promotes this entry module independently.
import intidentity


def selected() -> int:
    value = int("7000")
    intidentity.keep(value)
    return value


value = selected()
intidentity.churn()
intidentity.keep(value)
intidentity.check("return to caller")


def forwarded(value: int) -> int:
    return value


intidentity.keep(value)
intidentity.keep(forwarded(value))
intidentity.check("forwarded return")
