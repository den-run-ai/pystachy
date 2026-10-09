# error: an annotation that is not a type is not supported: only classes, typing's names, their subscripts and '|' of them (CPython evaluates this annotation when the def statement runs
def first(x: [t for t in [int]][0]) -> int:
    return x


print(first(1))
