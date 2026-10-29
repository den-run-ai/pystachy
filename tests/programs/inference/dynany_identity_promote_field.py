# No opt-in here: the python-int gate promotes this entry module independently.
import intidentity


class Box:
    def __init__(self, value: int) -> None:
        self.value = value


value = int("5000")
box = Box(value)
intidentity.keep(box.value)
intidentity.churn()
intidentity.keep(value)
intidentity.check("typed field")
intidentity.fields("Any field", box, value)
box.value = box.value
intidentity.fields("field self store", box, value)
copy = Box(box.value)
box.value = int("5000")
intidentity.churn()
intidentity.fields("copied field", copy, value)
intidentity.keep(copy.value)
intidentity.keep(box.value)
intidentity.check("field replacement")
box.value = alias = int("5100")
intidentity.keep(box.value)
intidentity.churn()
intidentity.keep(alias)
intidentity.check("field and local chain")
intidentity.fields("chained Any field", box, alias)
