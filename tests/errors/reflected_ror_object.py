# error: reflected_ror_object.py:16: error: reflected operator methods are not supported (Name | Flag calls Flag.__ror__)
# Name has no __or__, so CPython calls Flag.__ror__(flag, name)
class Name:
    def __init__(self, s: str) -> None:
        self.s = s


class Flag:
    def __init__(self, on: bool) -> None:
        self.on = on

    def __ror__(self, o: Name) -> str:
        return o.s if self.on else ""


print(Name("x") | Flag(True))
