# No opt-in here: the python-int gate promotes this entry module independently.
import intidentity

value = int("6000")
maybe: int | None = value
intidentity.keep(maybe)
intidentity.churn()
intidentity.keep(value)
intidentity.check("optional copy")
if maybe is not None:
    intidentity.keep(maybe)
    intidentity.keep(value)
    intidentity.check("optional narrowed")
maybe = None
intidentity.keep(maybe)
intidentity.keep(None)
intidentity.check("optional None")


def optional(value: int | None) -> None:
    intidentity.keep(value)
    intidentity.churn()
    intidentity.keep(value)
    intidentity.check("optional parameter")


optional(int("6000"))
optional(None)


def shared(value: int | None) -> None:
    def read() -> int | None:
        if value is not None:
            return value
        return None

    def clear() -> None:
        nonlocal value
        value = None

    if value is not None:
        intidentity.keep(value)
        intidentity.churn()
        intidentity.keep(read())
        intidentity.check("narrowed shared optional")
        print("shared optional payload", value)
    clear()
    print("shared optional cleared", read() is None)


shared(int("6100"))
shared(None)
