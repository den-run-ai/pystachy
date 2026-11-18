# error: calling a class object that may be any class's (type[object]) is not supported
class A:
    pass


class C:
    pass


def make(k: type[object]):
    return k()


print(make(A))
