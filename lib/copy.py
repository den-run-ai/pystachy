"""Generic (shallow and deep) copying operations.

Interface summary:

        import copy

        x = copy.copy(y)                # make a shallow copy of y
        x = copy.deepcopy(y)            # make a deep copy of y
        x = copy.replace(y, a=1, b=2)   # new object with fields replaced, as defined by `__replace__`

For module specific errors, copy.Error is raised.

The difference between shallow and deep copying is only relevant for
compound objects (objects that contain other objects, like lists or
class instances).

- A shallow copy constructs a new compound object and then (to the
  extent possible) inserts *the same objects* into it that the
  original contains.

- A deep copy constructs a new compound object and then, recursively,
  inserts *copies* into it of the objects found in the original.

Two problems often exist with deep copy operations that don't exist
with shallow copy operations:

 a) recursive objects (compound objects that, directly or indirectly,
    contain a reference to themselves) may cause a recursive loop

 b) because deep copy copies *everything* it may copy too much, e.g.
    administrative data structures that should be shared even between
    copies

Python's deep copy operation avoids these problems by:

 a) keeping a table of objects already copied during the current
    copying pass

 b) letting user-defined classes override the copying operation or the
    set of components copied

This version does not copy types like module, class, function, method,
nor stack trace, stack frame, nor file, socket, window, nor any
similar types.

Classes can use the same interfaces to control copying that they use
to control pickling: they can define methods called __getinitargs__(),
__getstate__() and __setstate__().  See the documentation for module
"pickle" for information on these methods.
"""

# Pystachy's subset implementation of CPython 3.13.16's Lib/copy.py (lib/compatibility.md#copy).
# CPython's module dispatches on type(x) and on the pickling protocol (__reduce_ex__ and copyreg),
# which a compiled program has no run-time form of: here the static type of the value selects
# what to copy, as isinstance() of a type that rules the value's out is decided as the program
# compiles, with CPython's results for the types it copies. A list, dict, set or frozenset is
# copied item by item, an object of a class of the program slot by slot (or by its __copy__ and
# __deepcopy__ methods), and a number, a str, bytes, None or a function is its own copy. A deep
# copy keeps the copy of each container and object it copies in its memo, so that shared objects
# stay shared and cycles are copied as cycles, and gives a tuple its items' copies, or the tuple
# itself where no item changed, as CPython does.
from _pystachy_copy import _Memo, _memo_get, _memo_put


class Error(Exception):
    pass
error = Error   # backward compatibility

__all__ = ["Error", "copy", "deepcopy"]  # (CPython 3.13 adds replace(), which is not here)


def copy(x):
    """Shallow copy operation on arbitrary Python objects.

    See the module's __doc__ string for more info.
    """
    if __pys_copy_is_own(x):
        # (a number, a str, bytes, None, a tuple, a frozenset or a function, as CPython's
        # _copy_immutable gives it: decided as the program compiles but for None and Any values.
        # This return comes first, so that the function returns x's type)
        return x
    if isinstance(x, list):
        return x.copy()
    if isinstance(x, dict):
        return x.copy()
    if __pys_copy_is_object(x):
        # (an object of a class: its __copy__(), or a new object of its class with its slots; an
        # Any value of another kind than those above raises here, before the set below)
        return __pys_copy_object(x)
    if isinstance(x, set):
        return x.copy()
    return x


def deepcopy(x, memo: _Memo | None = None):
    """Deep copy operation on arbitrary Python objects.

    See the module's __doc__ string for more info.
    """
    # (memo is a deep copy's memo, which a __deepcopy__() method is given to pass on; CPython's
    # _nil parameter, a private sentinel, is not here)
    if memo is None:
        return _deepcopy(x, _Memo())
    return _deepcopy(x, memo)


def _deepcopy(x, memo: _Memo):
    # the deep copy of x, with the copies of the containers and objects copied so far in memo:
    # CPython's deepcopy(), whose _deepcopy_dispatch table is x's static type here. Each kind's
    # copy is a function of its own, as in CPython, which an Any value's several kinds need: it
    # compiles each that the value's kinds may take, each with its locals' own types
    if __pys_deepcopy_is_own(x):
        # (a number, a str, bytes, None, a function or a tuple of such values, as CPython's
        # _deepcopy_atomic and _deepcopy_tuple give it. This return comes first, so that each
        # specialization returns x's type before it copies values that may hold one of that type)
        return x
    if isinstance(x, list):
        return _deepcopy_list(x, memo)
    if isinstance(x, dict):
        return _deepcopy_dict(x, memo)
    if isinstance(x, tuple):
        return _deepcopy_tuple(x, memo)
    if __pys_copy_is_object(x):
        # (an object of a class: the memo's copy of it; else its __deepcopy__(memo), or a new
        # object of its class, which the memo holds before its fields become their deep copies.
        # An Any value of another kind than those above raises here, before the sets below,
        # which no Any value holds)
        return __pys_deepcopy_object(x, memo)
    if isinstance(x, set):
        return _deepcopy_set(x, memo)
    if isinstance(x, frozenset):
        return _deepcopy_frozenset(x, memo)
    return x


# Each of the functions below returns the memo's copy of x first, as CPython's deepcopy() does
# before it calls them, and so returns x's type before it copies x's items.

def _deepcopy_list(x, memo: _Memo):
    hit = _memo_get(memo, x)
    if hit is not None:
        return hit
    y = x.copy()
    y.clear()
    _memo_put(memo, x, y)
    for a in x:
        y.append(_deepcopy(a, memo))
    return y


def _deepcopy_dict(x, memo: _Memo):
    hit = _memo_get(memo, x)
    if hit is not None:
        return hit
    y = x.copy()
    y.clear()
    _memo_put(memo, x, y)
    for key, value in x.items():
        y[_deepcopy(key, memo)] = _deepcopy(value, memo)
    return y


def _deepcopy_set(x, memo: _Memo):
    # (as CPython copies a set through its __reduce__: a list of its items, then their copies, then
    # the new set of them, which the memo then holds; a hook that changes x changes none of these)
    hit = _memo_get(memo, x)
    if hit is not None:
        return hit
    copies = [_deepcopy(a, memo) for a in list(x)]
    y = x.copy()
    y.clear()
    for a in copies:
        y.add(a)
    _memo_put(memo, x, y)
    return y


def _deepcopy_frozenset(x, memo: _Memo):
    # (a new frozenset of its items' copies, as CPython's __reduce__ of a frozenset makes it)
    hit = _memo_get(memo, x)
    if hit is not None:
        return hit
    y = frozenset([_deepcopy(a, memo) for a in x])
    _memo_put(memo, x, y)
    return y


def _deepcopy_tuple(x, memo: _Memo):
    # (its items' copies, or x itself where none changed: CPython's _deepcopy_tuple)
    hit = _memo_get(memo, x)
    if hit is not None:
        return hit
    return __pys_deepcopy_tuple(x, memo)


def _deepcopy_items(x, memo: _Memo):
    # the deep copy of a runtime-length tuple of items that are not their own copies (CPython's
    # _deepcopy_tuple): the memo's copy, where an item's copy made one, else x where every item is
    # its own copy, else a new tuple of the copies, which the memo then holds
    if len(x) == 0:
        return x  # (also first, so that the function returns x's type before its items' copies)
    y = [_deepcopy(a, memo) for a in x]
    hit = _memo_get(memo, x)
    if hit is not None:
        return hit
    for i in range(len(x)):
        if x[i] is not y[i]:
            t = tuple(y)
            _memo_put(memo, x, t)
            return t
    return x
