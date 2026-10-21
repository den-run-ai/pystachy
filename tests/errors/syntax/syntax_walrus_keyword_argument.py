# error: syntax_walrus_keyword_argument.py:3: error: invalid syntax
def f(x):
    return g(k=n := x)


print("ran")
