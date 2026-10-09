# Documented deviation: ints are 64-bit, so checked arithmetic raises OverflowError where CPython
# would switch to a big int. It is an exception like the others: an except clause catches it, and
# finally blocks run before an uncaught one ends the program.


def grow(n: int) -> int:
    total = 1
    for i in range(n):
        total = total * 1000000
    return total


for n in [2, 4]:
    try:
        print(grow(n))
    except OverflowError as e:
        print("caught:", e)
try:
    x = 2 ** 62
    print(x * 2)
finally:
    print("finally runs first")
