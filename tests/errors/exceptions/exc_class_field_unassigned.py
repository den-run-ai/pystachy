# error: Sub.__init__ may leave field 'code' of Base unassigned where it is read: assign it, or call super().__init__(...) first
class Base(Exception):
    def __init__(self, code: int):
        super().__init__(code)
        self.code = code

    def show(self) -> str:
        return f"code {self.code}"


class Sub(Base):
    def __init__(self, name: str):
        self.name = name


print(Sub("x").show())
