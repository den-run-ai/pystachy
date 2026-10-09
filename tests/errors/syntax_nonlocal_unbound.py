# error: syntax_nonlocal_unbound.py:4: error: no binding for nonlocal 'zz' found
def f(x):
    def g(y):
        nonlocal zz


print("ran")
