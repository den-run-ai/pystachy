# error: the default value of parameter 'opt' of g() cannot be typed here, before its def statement runs; annotate the parameter
import sys


def t(x):
    return g(x)


if len(sys.argv) > 5:
    print(t(1))
for W in range(3):
    pass


def g(x, opt=W):
    return x + opt


print(t(1))
