# error: decorated_redefinition.py:11: error: redefinition of 'f' is not supported
def deco(g):
    return g


@deco
def f() -> int:
    return 1


def f() -> int:
    return 2


print(f())
