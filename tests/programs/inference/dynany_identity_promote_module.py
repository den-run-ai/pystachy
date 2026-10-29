# No opt-in here: the python-int gate promotes this entry module independently.
import intidentity

value = int("3000")
alias = value
intidentity.keep(value)
intidentity.churn()
intidentity.keep(alias)
intidentity.check("module copy")
value = int("3000")
intidentity.keep(value)
intidentity.keep(alias)
intidentity.check("equal replacement")
left = right = int("3100")
intidentity.keep(left)
intidentity.churn()
intidentity.keep(right)
intidentity.check("chained copy")


def read_global() -> None:
    intidentity.keep(alias)
    intidentity.churn()
    intidentity.keep(alias)
    intidentity.check("global read")


read_global()
