# error: syntax_walrus_argument.py:3: error: invalid syntax
def f(x):
    return g(x.y := 1)


print("ran")
