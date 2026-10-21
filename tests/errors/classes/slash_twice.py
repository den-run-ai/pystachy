# error: / may appear only once
def f(a, /, /, b):
    return [a, b]


print(f(1, 2))
