# == and != of a complex number and a value typed as a class whose subclass compares with complex
# numbers: the object's runtime class decides, in both orders and in tuple search; an object of
# the base class, which has no __eq__, is compared by identity
class Base:
    pass


class Match(Base):
    def __eq__(self, other: complex) -> bool:
        return True


class Other(Base):
    def __ne__(self, other: complex) -> bool:
        return False


def get(k: int) -> Base:
    if k == 0:
        return Match()
    if k == 1:
        return Other()
    return Base()


for k in range(3):
    x = get(k)
    print(x == 1j, 1j == x, x != 1j, 1j != x, x in (1j,), 1j in (x,))
