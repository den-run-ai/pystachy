# What an __init__ reads of its object before it calls super().__init__() (str(self),
# repr(self), a method or property that formats it, a function given self, a closure) shows the
# arguments the object was made with; super().__init__() then replaces them.
def describe(e: "Passed") -> str:
    return "D:" + str(e)


class Early(Exception):
    def __init__(self, a: int, b: int) -> None:
        self.before = str(self)
        self.rbefore = repr(self)
        super().__init__(a + b)


class ByMethod(ValueError):
    def __init__(self, a: int, b: int) -> None:
        self.note = self.describe()
        super().__init__(a - b)

    def describe(self) -> str:
        return "was " + str(self)


class ByProperty(ValueError):
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.shown = self.text
        super().__init__(a * b)

    @property
    def text(self) -> str:
        return "text " + str(self)


class Passed(ValueError):
    def __init__(self, a: int, b: int) -> None:
        self.d = describe(self)
        super().__init__(a * b)


class Closure(ValueError):
    def __init__(self, a: int, b: int) -> None:
        f = lambda: repr(self)
        self.early: str = f()
        super().__init__(a)


class InCall(ValueError):
    def __init__(self, a: int, b: int) -> None:
        super().__init__(str(self) + "!")


e = Early(1, 2)
print(e.before, e.rbefore, str(e), repr(e))
m = ByMethod(5, 3)
print(m.note, str(m), repr(m))
p = ByProperty(2, 3)
print(p.shown, str(p))
d = Passed(3, 4)
print(d.d, str(d))
c = Closure(6, 7)
print(c.early, str(c))
print(str(InCall(8, 9)), repr(InCall(1, 0)))
