# error: union_same_kind.py:3: error: a union of list[int] and list[str] is not supported: isinstance() cannot tell them apart (a union of the types they hold may do: list[A | B])
# two members that isinstance() cannot tell apart
x: list[int] | list[str] = [1]
print(x)
