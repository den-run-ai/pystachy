"""Experimental collector-backed _weakref subset; see docs/prototypes/weakref.md.

Pystachy loads this file for the builtin _weakref module. The private compiler
primitives create an atomic, unscanned handle and read its nullable target.
The class's fields are this module's own: a program sees CPython's interface,
in which a reference has no such attributes. This module is not a port of the
full weakref module.
"""
from typing import Generic, TypeVar

_T = TypeVar("_T")


class ReferenceType(Generic[_T]):
    def __init__(self, obj: _T) -> None:
        if obj is None:
            raise TypeError("cannot create weak reference to 'NoneType' object")
        self._handle = __pys_weakref_new(obj)
        self._hash = -1  # (hash() of the referent, once computed; CPython's hash is never -1)

    def __call__(self) -> _T | None:
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
