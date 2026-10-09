# error: exceptions must derive from BaseException: raise needs an exception class or a call of one
def f(n: int) -> None:
    raise n


f(3)
