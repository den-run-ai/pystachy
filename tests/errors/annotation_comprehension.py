# error: a lambda or comprehension in an annotation is not supported (CPython evaluates this annotation when the def statement runs
def first(x: [t for t in [int]][0]) -> int:
    return x


print(first(1))
