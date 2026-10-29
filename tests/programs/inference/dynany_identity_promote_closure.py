# No opt-in here: the python-int gate promotes this entry module independently.
import intidentity


def escaped():
    value = int("9000")

    def read() -> None:
        intidentity.keep(value)

    read()
    return read


reader = escaped()
intidentity.churn()
reader()
intidentity.check("escaped cell")


def replaced() -> None:
    value = int("9000")

    def read() -> None:
        intidentity.keep(value)

    def write() -> None:
        nonlocal value
        value = int("9000")

    read()
    write()
    intidentity.churn()
    read()
    intidentity.check("replaced cell")
    read()
    intidentity.keep(value)
    intidentity.check("current cell")


replaced()
