# A class-body value that reads the body's constant runs as CPython's does where the class
# statement runs: 1 // n raises ZeroDivisionError there, before the module's later code.
print("before")


class Ratio:
    n = 0
    half = 1 // n


print("never")
