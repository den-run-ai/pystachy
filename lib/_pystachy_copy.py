"""copy.deepcopy()'s memo, for Pystachy's lib/copy.py.

CPython's memo is a dict from the id() of each object copied so far to its copy, which also keeps
the originals alive (_keep_alive), so that no id is reused while the copy runs. Here a memo is an
object of _Memo, whose fields are this module's own (specs.OPAQUE): the index maps each original's
address to the place of its copy in _keep, which holds the originals and the copies as references
that the collector scans, whatever their types. Only _memo_get() and _memo_put() read and write
them, through the compiler's private primitives of this module, each copy as the type of its
original: the copy of an object has its original's class, of a container its original's type.
Programs do not import this module; a program's __deepcopy__() gets the memo to pass on.
"""

__all__: list[str] = []


class _Memo:
    def __init__(self) -> None:
        self._index: dict[int, int] = {}
        self._keep: list[str] = []


def _memo_get(memo: _Memo, x):
    # the copy of x made so far in this deep copy, of x's type, or None
    i = memo._index.get(__pys_copy_addr(x), -1)
    if i < 0:
        return None
    return __pys_copy_unref(memo._keep[i], x)


def _memo_put(memo: _Memo, x, y) -> None:
    # remember y as the copy of x, and keep both alive
    memo._keep.append(__pys_copy_ref(x))
    memo._index[__pys_copy_addr(x)] = len(memo._keep)
    memo._keep.append(__pys_copy_ref(y))
