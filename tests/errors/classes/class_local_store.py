# error: class_local_store.py:9: error: local variable 'A' is read before its first assignment; declare it first (A: T)
# An assignment to a class attribute through such a name (class_local_call.py): CPython raises
# UnboundLocalError and A.k stays 7
class A:
    k: int = 7


def g() -> None:
    A.k += 2
    A = 5


g()
print(A.k)
