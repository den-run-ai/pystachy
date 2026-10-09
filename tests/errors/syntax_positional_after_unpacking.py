# error: syntax_positional_after_unpacking.py:3: error: positional argument follows keyword argument unpacking
def f(k, a):
    return g(**k, a)


print("ran")
