# error: syntax_keyword_unpacking.py:3: error: cannot assign to keyword argument unpacking
def f(x):
    return g(**x=1)


print("ran")
