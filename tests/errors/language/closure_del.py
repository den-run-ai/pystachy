# error: closure_del.py:4: error: show() reads 'x', which del unbinds: not supported
def f(x):
    x = x + 1
    def show():
        return x
    del x
    return show


print(f(1)())
