# A field that __init__ may leave unassigned, read through a template hierarchy's value: CPython's
# AttributeError names the object's own class, also one of a specialization made after the error
# message's table of class names (#962).
class Base:
    def __init__(self, value, extra: bool):
        if extra:
            self.more = value
        self.value = value


class Sub(Base):
    pass


def read(x) -> str:
    try:
        return str(x.more)
    except AttributeError as e:
        return str(e)


xs = [Base(1, True), Base(2, False), Sub(3, True), Sub(4, False)]
for x in xs:
    print(read(x))
ys = [Base("a", False), Sub("b", False), Sub("c", True)]
for y in ys:
    print(read(y))
