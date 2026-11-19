# error: object_sentinel_comprehension_arg.py:10: error: expected int, got object
# CPython prints [False]: the comprehension's S is another object(), not the sentinel
S = object()


def g(x: int = S) -> bool:
    return True if x is S else False


print([g(S) for S in [object()]])
