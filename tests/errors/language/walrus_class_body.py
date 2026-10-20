# error: walrus_class_body.py:6: error: an assignment expression (:=) in a class body is not supported (CPython binds a class attribute)
# (in a comprehension there, CPython rejects it itself)


class C:
    y: int = (z := 1)


print(C().y)
