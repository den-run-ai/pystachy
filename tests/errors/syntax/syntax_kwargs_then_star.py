# error: syntax_kwargs_then_star.py:3: error: iterable argument unpacking follows keyword argument unpacking
def f(x, k):
    return g(**k, *x)


print("ran")
