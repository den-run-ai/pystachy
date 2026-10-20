# An exception class's __init__ calls a method of its base through super() before
# super().__init__() assigns the base's fields. super() dispatches statically, so only the fields
# that method reads matter: one that reads none, a static method and BaseException's __str__
# leave the base's unassigned fields unread, and each program runs as in CPython (#571).


class AppError(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.msg = msg

    def fmt(self, code: int) -> str:
        return "error code " + str(code)

    @staticmethod
    def sfmt(code: int) -> str:
        return "static code " + str(code)


class CodeError(AppError):
    def __init__(self, code: int) -> None:
        super().__init__(super().fmt(code))
        self.code = code


class StaticError(AppError):
    def __init__(self, code: int) -> None:
        super().__init__(super().sfmt(code))


class StrError(AppError):
    def __init__(self) -> None:
        print(repr(super().__str__()))
        super().__init__("str")


try:
    raise CodeError(42)
except AppError as e:
    print(e, e.msg)

try:
    raise StaticError(7)
except AppError as e:
    print(e, e.msg)

s = StrError()
print(s, s.msg)


class B(Exception):
    def __init__(self) -> None:
        self.s = "x"

    def m(self) -> int:
        return 7

    def size(self) -> int:
        return len(self.s)


class C(B):
    def __init__(self) -> None:
        print(super().m())
        super().__init__()


c = C()
print(c.size())
