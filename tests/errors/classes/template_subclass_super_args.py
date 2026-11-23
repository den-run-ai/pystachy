# error: the types of the arguments of super().__init__(...) in Child.__init__ must be known where class Child is declared
# The arguments of super().__init__(...) decide which specialization of the class template the
# subclass's objects begin as, before any code is compiled: a value whose type only compiling
# the code that makes it tells (a call of a function without a return annotation) cannot.
class Base:
    def __init__(self, value):
        self.value = value


def make(n: int):
    return [n, n]


class Child(Base):
    def __init__(self, n: int) -> None:
        super().__init__(make(n))


print(Child(2).value)
