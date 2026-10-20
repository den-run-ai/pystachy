# A module global first None, then an object, read first in a function compiled before
# the one that assigns it.
class Conn:
    def __init__(self, name: str) -> None:
        self.name = name


current = None


def name() -> str:
    c = current
    return "none" if c is None else c.name


def connect(n: str) -> None:
    global current
    current = Conn(n)


print(name())
connect("db")
print(name())
