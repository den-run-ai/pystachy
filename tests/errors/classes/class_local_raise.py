# error: class_local_raise.py:8: error: local variable 'E' is read before its first assignment; declare it first (E: T)
# raise reads its exception class (class_local_call.py)
class E(Exception):
    pass


def g() -> None:
    raise E("x")
    E = 5


g()
