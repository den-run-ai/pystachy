# == and != with a union holding complex numbers and ints on the left and an object whose class
# defines __eq__ on the right: int's and complex's own comparison decline the object, so its
# __eq__ answers, and its inherited __ne__ negates that
class Equal:
    def __eq__(self, other: object) -> bool:
        print("Equal.__eq__")
        return True


def f(v: int | complex) -> None:
    e = Equal()
    print(v == e, v != e)


f(1j)
f(1)
