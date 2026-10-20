# error: cannot infer the type of an empty list; add a type annotation
def f():
    value = 3
    value = []
    return value
print(f())
