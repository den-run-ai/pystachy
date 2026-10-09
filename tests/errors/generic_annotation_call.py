# error: a call in an annotation is not supported (CPython evaluates this annotation when the def statement runs
def note(s):
    print("note", s)
    return int


def first[T](xs: note(T)) -> T:
    return xs
