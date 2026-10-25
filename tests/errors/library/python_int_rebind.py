# error: python-int prototype does not support rebinding builtin int
# pystachy: python-int
def f(int):
    return int
print(f(1))
