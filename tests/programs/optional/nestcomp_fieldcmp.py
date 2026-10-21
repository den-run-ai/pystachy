# A function compiled in the middle of another's compile leaves that compile as it was (#822):
# here make_b(int), compiled while a.f is None is typed (dry() of make_b(1).f = 1). Its own field
# read leaves a.f is None a comparison of the field's value, which is 5 after a.set(5).
class A:
    def __init__(self):
        self.f = None

    def set(self, v):
        self.f = v


class B:
    def __init__(self):
        self.f = 0
        self.g = 0


def make_b(n):
    b = B()
    b.g = n
    print(b.g)
    return b


a = A()
for i in range(2):
    print(a.f is None)
    a.set(5)
make_b(1).f = 1
