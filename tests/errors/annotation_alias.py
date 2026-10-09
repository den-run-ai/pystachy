# error: annotation_alias.py:6: error: unsupported type annotation
# A type alias is not supported; its name is bound before the def, so it is not a NameError.
IntList = list[int]


def f(x: IntList) -> int:
    return len(x)


print(f([1, 2]))
