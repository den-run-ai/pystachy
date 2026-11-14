# == and != of a union holding complex numbers and a value typed as a class whose subclass
# defines __eq__: the object's runtime class decides, for each member of the union, in both
# orders and in tuple search; an object of the base class compares by identity
class Base:
    pass


class Match(Base):
    def __eq__(self, other: object) -> bool:
        return True


def get(k: int) -> Base:
    if k == 0:
        return Match()
    return Base()


def check(v: int | complex) -> None:
    for k in range(2):
        x = get(k)
        print(x == v, x != v, v == x, v != x, x in (v,), v in (x,))


check(1)
check(1j)
