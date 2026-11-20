# pystachy: python-int
# x is y or x == y, the identity-or-equality test of operator.indexOf() and countOf(), on
# promoting ints: x == y, as on other numbers (where x is y alone is a compile-time error:
# tests/errors/numbers/python_int_is.py)
import operator


def same(x, y):
    return x is y or x == y


big = 2 ** 70
print(same(big, big + 0), same(big, big + 1), same(3, 3), same(3, 3.0), same(big, float(big)), same(True, 1))
a = big
b = big + 1
if a is b or a == b:
    print("equal")
else:
    print("unequal")
print(operator.indexOf([1, 2, 3], 3), operator.countOf([5, 1, 5], 5))
