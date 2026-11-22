# error: making the specialization of class template Sem that Bounded derives from, where it is declared, before any code is compiled
# (after "cannot infer the type of field 'lock'"): the specialization that a subclass with an
# __init__ of its own derives from is made where the classes are declared, before any code is
# compiled, and a field of it that holds an object of a class template, which only compiled code
# makes, has no type there (threading's Semaphore and BoundedSemaphore without the dynamic Any
# opt-in).
class Lock:
    def __init__(self, owner):
        self.owner = owner


class Sem:
    def __init__(self, value: int) -> None:
        self.lock = Lock(value)
        self.value = value


class Bounded(Sem):
    def __init__(self) -> None:
        super().__init__(1)


print(Bounded().value)
