# error: an annotation that is not a type is not supported: only classes, typing's names, their subscripts and '|' of them (CPython evaluates this annotation when the def statement runs
def note(s):
    print("note", s)
    return int


def first[T](xs: note(T)) -> T:
    return xs
