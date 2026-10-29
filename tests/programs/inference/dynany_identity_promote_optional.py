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
