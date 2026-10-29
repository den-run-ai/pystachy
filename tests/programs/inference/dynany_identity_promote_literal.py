# No opt-in here: the python-int gate promotes this entry module independently.
# CPython shares these equal literal constants within one compiled module.
import intidentity


class Box:
    def __init__(self) -> None:
        self.value: int = 1000


box = Box()
intidentity.keep(box.value)
intidentity.keep(1000)
intidentity.check("literal field")


def local() -> None:
    value: int = 1000
    intidentity.keep(value)
    intidentity.keep(1000)
    intidentity.check("literal local")
    maybe: int | None = 1000
    intidentity.keep(maybe)
    intidentity.keep(1000)
    intidentity.check("literal optional")


def default(value: int = 1000) -> None:
    intidentity.keep(value)
    intidentity.keep(1000)
    intidentity.check("literal default")


local()
default()
