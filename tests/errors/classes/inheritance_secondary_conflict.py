# error: both bases declare method 'size'
# Two secondary bases that declare one method, which the class does not override: CPython's
# method resolution order takes the first's (1)
class Base:
    pass


class First:
    def size(self) -> int:
        return 1


class Second:
    def size(self) -> int:
        return 2


class Both(Base, First, Second):
    pass


print(Both().size())
