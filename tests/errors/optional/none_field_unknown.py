# error: none_field_unknown.py:12: error: cannot infer the type of field 'v' from None here, before a value of another type is assigned to it; annotate it (self.v: T | None = None)
# A field first None, read where its type is needed, which only a template's method
# (its parameter has no annotation, and nothing calls it) gives another value.
class C:
    def __init__(self) -> None:
        self.v = None

    def put(self, x) -> None:
        self.v = x

    def size(self) -> int:
        return len(self.v)


print(C().size())
