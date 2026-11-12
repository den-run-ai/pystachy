# error: object_sentinel_param_other.py:13: error: expected list[int], got object
# A sentinel parameter (annotated T, its default a module's sentinel) takes a T or that sentinel:
# another object() is no list[int] (CPython raises TypeError at its len(), and mypy rejects the call).
_dummy = object()
_other = object()


def size(items: list[int] = _dummy) -> int:
    return len(items) if items is not _dummy else -1


print(size(), size([1]))
print(size(_other))
