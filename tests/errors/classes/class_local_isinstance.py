# error: class_local_isinstance.py:8: error: local variable 'A' is read before its first assignment; declare it first (A: T)
# isinstance() reads its classes (class_local_call.py), also where the static types decide the test
class A:
    k: int = 7


def g(o: A) -> None:
    print(isinstance(o, A))
    A = 5


g(A())
