"""Experimental collector-backed _weakref subset; see docs/prototypes/weakref.md.

Pystachy loads this file for the builtin _weakref module. The private compiler
primitives create an atomic, unscanned handle and read its nullable target.
This module is not a port of the full weakref module.
"""
from typing import Generic, TypeVar

_T = TypeVar("_T")


class ref(Generic[_T]):
    def __init__(self, obj: _T) -> None:
        if obj is None:
            raise TypeError("cannot create weak reference to 'NoneType' object")
        self._handle = __pys_weakref_new(obj)

    def __call__(self) -> _T | None:
        return __pys_weakref_get(self._handle)

    def __eq__(self, other) -> bool:
        raise NotImplementedError("weak reference equality is not supported by this prototype")

    def __ne__(self, other) -> bool:
        raise NotImplementedError("weak reference equality is not supported by this prototype")

    def __hash__(self) -> int:
        raise NotImplementedError("weak reference hashing is not supported by this prototype")


ReferenceType = ref
