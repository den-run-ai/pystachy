# error: expected int, got str
from adapter import TypedIterator, typed_iterator

values: TypedIterator[int] = typed_iterator(["wrong"])
print(next(values))
