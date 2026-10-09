# error: syntax_nonlocal_param.py:4: error: name 'y' is parameter and nonlocal
def f(x):
    def g(y):
        nonlocal y


print("ran")
