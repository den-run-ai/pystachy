# error: exc_classmethod_default.py:16: error: calling class method S.make() is not supported: it uses cls, and is compiled only for B, which defines it (a class that inherits it has its own only where no default value of it is evaluated when its def runs, and in the same module)
def start() -> list[str]:
    return ["start"]


class B(Exception):
    @classmethod
    def make(cls, log: list[str] = start()) -> "B":
        return cls(str(log))


class S(B):
    pass


print(type(S.make()).__name__)
