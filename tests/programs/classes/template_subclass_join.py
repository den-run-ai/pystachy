# A field of a class template's specialization that its subclasses' methods give a value of
# another type: the field of the specialization and of its subclasses' objects holds both, as a
# field that __init__'s argument types holds what later code stores (#962).
class Slot:
    def __init__(self, value):
        self.value = value

    def show(self) -> str:
        return "slot " + str(self.value)


class Clearable(Slot):
    def clear(self) -> None:
        self.value = None


class Reset(Slot):
    def __init__(self) -> None:
        super().__init__(5)

    def reset(self) -> None:
        self.value = None


c = Clearable(3)
print(c.show())
c.clear()
print(c.show(), c.value is None)
r = Reset()
print(r.show())
r.reset()
print(r.show())
items = [Slot(1), Clearable(2), Reset()]
for x in items:
    print(x.show())
