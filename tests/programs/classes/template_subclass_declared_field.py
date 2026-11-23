# A field of a class template's specialization that holds an object of another class template,
# where the specialization is made as its classes are declared, before any code is compiled: the
# one that a subclass with an __init__ of its own derives from (#962). The object's class is the
# specialization that its arguments' types make there (threading's Semaphore, whose Condition
# holds a Lock, and BoundedSemaphore, without the dynamic Any opt-in).
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


b = Bounded()
s = Sem(3)
print(b.value, b.lock.owner, s.lock.owner + 1, isinstance(b, Sem))
for x in [s, b]:
    print(x.value, x.lock.owner)
