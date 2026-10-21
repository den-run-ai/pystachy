# error: nestcomp_nonecmp_leak.py:11: error: cannot infer the type of 'y' from None here, before a value of another type is assigned to it; annotate it (y: T | None) (compiling g(int) for the call at
# A function compiled in the middle of another's compile is compiled as it would be on its own
# (#822): here g(int), compiled while f's read in x is None is in progress. g's own "if y:" reads
# a local that only None has been assigned so far, whose next value cannot be typed there: it is
# rejected, as it is where g is compiled on its own. Before #822 it was compiled as a comparison
# with None, and printed "y is falsy" three times where CPython prints "y is falsy" and then
# "y is truthy" twice.
def g(n):
    y = None
    for i in range(n):
        if y:
            print("y is truthy")
        else:
            print("y is falsy")
        w = i * 10 + 5
        y = w


def f():
    x = None
    if x is None:
        print("x is None")
    x = g(3)
    if x is None:
        print("x still None")


f()
