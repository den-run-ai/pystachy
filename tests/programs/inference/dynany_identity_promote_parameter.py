# No opt-in here: the python-int gate promotes this entry module independently.
import intidentity


def twice(value: int) -> None:
    intidentity.keep(value)
    intidentity.churn()
    intidentity.keep(value)
    intidentity.check("parameter twice")


def once(value: int) -> None:
    intidentity.churn()
    intidentity.keep(value)


twice(int("4000"))
value = int("4000")
intidentity.keep(value)
once(value)
intidentity.check("caller to parameter")
