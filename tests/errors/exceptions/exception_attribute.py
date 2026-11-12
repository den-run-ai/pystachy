# error: reading exception args requires dynamic Any (# pystachy: dynamic-any)
try:
    print(int("x"))
except ValueError as e:
    print(e.args)
