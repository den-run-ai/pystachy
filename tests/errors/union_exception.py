# error: union_exception.py:7: error: an exception class (Oops) in a union (A | B) is not supported
# an exception class as a member
class Oops(Exception):
    pass


def f(x: Oops | int) -> None:
    print(x)
