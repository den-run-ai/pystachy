# __debug__ is True (CPython runs without -O), also in a function.
def check() -> bool:
    return __debug__


if __debug__:
    print("debug", check())
print(not __debug__)
