# error: cannot infer the type of 'L', an empty list so far: annotate it (L: list[T] = [])
import sys


def show(x):
    return str(x) + str(L)


if len(sys.argv) > 3:
    print(show(1))
L = []
L.append(show(2))
print(L, show(3))
