# error: union_attr_store_new.py:20: error: type A | B has no attribute 'y'
# CPython adds y to an A, which has a __dict__; A's native layout has no such field, as one class's
class A:
    def __init__(self) -> None:
        self.x = 1


class B:
    def __init__(self) -> None:
        self.x = 2
        self.y = 3


def pick(flag: int) -> A | B:
    return A() if flag == 0 else B()


for i in range(2):
    z = pick(i)
    z.y = 5
    print(z.y)
