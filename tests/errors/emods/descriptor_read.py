class Desc:
    def __init__(self) -> None:
        self.n = 0

    def __get__(self, obj: object, typ: object) -> int:
        print("get ran")
        return 1


class Holder:
    x: Desc = Desc()


class Reader:
    "CPython calls Desc.__get__ to read Holder.x when the def statement runs"

    def get(self, a=Holder.x):
        return a
