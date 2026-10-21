# A function compiled in the middle of another's compile leaves that compile as it was (#822):
# here make_a(int), compiled for the object of make_a(3).f is None, whose own comparison n > 2
# leaves the field read the operand of "is None".
class A:
    def __init__(self):
        self.f = None

    def set(self, v):
        self.f = v


def make_a(n):
    if n > 2:
        print("big")
    return A()


def main():
    if make_a(3).f is None:
        print("f is None")
    a = A()
    a.set(5)
    print(a.f)


main()
