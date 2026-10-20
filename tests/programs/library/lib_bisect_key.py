# lib/bisect.py's key= forms (CPython's Lib/bisect.py, unmodified), with a function as the key: key is
# a template's parameter, so 'if key is None:' is decided for each call, and key(a[mid]) is a call of
# the function the argument is
import bisect
from bisect import bisect_left, bisect_right, insort_left, insort_right


def neg(x):
    return -x


def second(p):
    return p[1]


rows = [("ann", 3), ("bob", 5), ("eve", 5), ("dan", 9)]
print(bisect_left(rows, 5, key=second), bisect_right(rows, 5, key=second), bisect.bisect(rows, 4, key=second))
print(bisect_left(rows, 9, 1, 3, key=second), bisect_right(rows, 0, lo=1, key=second))
desc = [9, 7, 7, 4, 1]
print(bisect_left(desc, -7, key=neg), bisect_right(desc, -7, key=neg))
insort_left(rows, ("cat", 5), key=second)
insort_right(rows, ("fox", 5), key=second)
bisect.insort(rows, ("gus", 1), key=second)
print(rows)
words = ["a", "bb", "ccc", "dddd"]
print(bisect_left(words, 3, key=len), bisect_right(words, 2, key=len))
insort_left(words, "zz", key=len)
print(words)
