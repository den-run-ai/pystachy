# error: reading __sizeof__ through a class object (type[A]) is not supported: the value may be NoneType's class object, which has its own __sizeof__
class A:
    __sizeof__ = 16


def size(k: type[A]) -> int:
    return k.__sizeof__


print(size(A))
