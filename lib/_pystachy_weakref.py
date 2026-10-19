"""Experimental collector-backed _weakref subset; see docs/prototypes/weakref.md.

Pystachy loads this file for the builtin _weakref module. The private compiler
primitives create an atomic, unscanned handle and read its nullable target.
The class's fields are this module's own: a program sees CPython's interface,
in which a reference has no such attributes. This module is not a port of the
full weakref module.
"""
import sys
from typing import Callable, Generic, TypeVar

_T = TypeVar("_T")


def _run_callbacks() -> None:
    # The callbacks of the references whose referents a collection has found dead, each once, in
    # the order CPython calls a referent's (its newest reference first). A collection runs no
    # code: they run here, where a reference is made or called, after the collection
    fire = __pys_weakref_fired()
    while fire is not None:
        fire()
        fire = __pys_weakref_fired()


class ReferenceType(Generic[_T]):
    def __init__(self, obj: _T, callback: "Callable[[ReferenceType[_T]], None] | None" = None, /) -> None:
        _run_callbacks()
        if obj is None:
            raise TypeError("cannot create weak reference to 'NoneType' object")
        self._hash = -1  # (hash() of the referent, once computed; CPython's hash is never -1)
        # (what the collector queues where the referent dies while this reference lives: the
        # reference keeps it, and it the reference and the callback; no field names the callback's
        # type, which names this class's)
        self._fire: Callable[[], None] | None = None
        if callback is None:
            self._handle = __pys_weakref_new(obj)
        else:
            cb = callback
            fire: Callable[[], None] = lambda: self._called(cb)
            self._fire = fire
            self._handle = __pys_weakref_new(obj, fire)

    def _called(self, callback: "Callable[[ReferenceType[_T]], None]") -> None:
        # The referent is dead: CPython's reference forgets its callback, then calls it with the
        # reference, and reports an exception it raises as one it ignores
        self._fire = None
        try:
            callback(self)
        except BaseException as e:
            # (CPython's report names the callback and shows the traceback; this shows the
            # exception's last line, as Pystachy shows an exception that nothing catches)
            m = str(e)
            print("Exception ignored while calling weakref callback:", file=sys.stderr)
            print(type(e).__name__ + (": " + m if m != "" else ""), file=sys.stderr)

    def __call__(self) -> _T | None:
        _run_callbacks()
        return __pys_weakref_get(self._handle)

    def __repr__(self) -> str:
        # CPython's: the referent's type by its fully qualified name, which leaves out
        # __main__ and builtins
        o = self()
        if o is None:
            return f"<weakref at {hex(__pys_weakref_addr(self))}; dead>"
        m = type(o).__module__
        t = type(o).__qualname__ if m == "__main__" or m == "builtins" else m + "." + type(o).__qualname__
        return f"<weakref at {hex(__pys_weakref_addr(self))}; to '{t}' at {hex(__pys_weakref_addr(o))}>"

    # CPython compares the referents while both are alive, else the references themselves;
    # None, which an optional reference's comparison passes, is never equal to a reference
    def __eq__(self, other: "ReferenceType[_T]") -> bool:
        if other is None:
            return False
        a = self()
        b = other()
        if a is None or b is None:
            return self is other
        return a == b

    def __ne__(self, other: "ReferenceType[_T]") -> bool:
        if other is None:
            return True
        a = self()
        b = other()
        if a is None or b is None:
            return self is not other
        return a != b

    # the referent's hash, kept once computed, so that it survives the referent
    def __hash__(self) -> int:
        if self._hash != -1:
            return self._hash
        o = self()
        if o is None:
            raise TypeError("weak object has gone away")
        self._hash = hash(o)
        return self._hash


ref = ReferenceType
