# error: class_local_attr.py:8: error: local variable 'A' is read before its first assignment; declare it first (A: T)
# A class attribute read through the name of a local assigned further on (class_local_call.py)
class A:
    k: int = 7


def g() -> None:
    x = A.k
    A = 5
    print(x, A)


g()
