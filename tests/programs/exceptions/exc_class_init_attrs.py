# Fields named as the attributes a builtin base's __init__ sets (StopIteration.value, AttributeError.name,
# ImportError.path, ...), assigned after that __init__ runs or where it never runs.
class S(StopIteration):
    def __init__(self, v: int) -> None:
        super().__init__("from-super")
        self.value = v
class A(AttributeError):
    def __init__(self, n: str) -> None:
        super().__init__("msg", name="ignored")
        self.name = n
        self.obj = 3
class B(A):
    def __init__(self) -> None:
        self.name = "b-first"
        super().__init__("b")
class I(ImportError):
    def __init__(self, p: str) -> None:
        ImportError.__init__(self, "cannot")
        self.path = p
class N(NameError):
    def __init__(self) -> None:
        self.name = "never-super"
class M(ModuleNotFoundError):
    def __init__(self, p: str) -> None:
        super(M, self).__init__(p)
        self.path = p
s = S(5)
print(s.value, str(s), repr(s))
a = A("n")
print(a.name, a.obj, str(a))
b = B()
print(b.name, repr(b))
i = I("/x")
print(i.path, str(i), repr(i))
print(N().name, M("/m").path)


# a class-body default shadows the builtin slot: CPython's instance keeps the field in its __dict__
class SD(StopIteration):
    value: int = 5

    def __init__(self, v: int) -> None:
        self.value = v
        super().__init__("x")


class TD(SD):
    def __init__(self) -> None:
        self.value = 9
        super().__init__(1)


class AD(AttributeError):
    name: str = "default-name"


class ID(ModuleNotFoundError):
    path: str = "/default"


print(SD(7).value, TD().value, AD("m").name, ID("no module").path)
