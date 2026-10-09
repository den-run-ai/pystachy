# error: syntax_nonlocal_annotated.py:5: error: annotated name 'x' can't be nonlocal
def f(x):
    def g():
        nonlocal x
        x: int = 1


print("ran")
