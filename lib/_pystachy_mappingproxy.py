"""The types module's MappingProxyType (Pystachy's own module).

MappingProxyType, the class CPython names mappingproxy (Objects/descrobject.c), is a read-only
view of a dict, which lib/types.py binds as types.MappingProxyType: it reads the dict's items as
they are when it is read, and has none of a dict's methods that change them.
"""
from typing import Generic, Iterator, Self, TypeVar

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class mappingproxy(Generic[_KT, _VT]):
    """Read-only proxy of a mapping."""

    # Pystachy port: CPython's takes any mapping but a list or a tuple, and passes each operation
    # on to it; this one takes a dict, whose types an annotation such as MappingProxyType[str, int]
    # names, and reads it as CPython's reads a dict

    def __init__(self, mapping: dict[_KT, _VT]) -> None:
        self._mapping = mapping

    def __getitem__(self, key: _KT, /) -> _VT:
        return self._mapping[key]

    def __contains__(self, key: _KT, /) -> bool:
        return key in self._mapping

    def __len__(self) -> int:
        return len(self._mapping)

    def __iter__(self) -> Iterator[_KT]:
        # the dict's keys, failing as its iterator does if it changes size
        for key in self._mapping:
            yield key

    def __reversed__(self) -> Iterator[_KT]:
        """D.__reversed__() -> reverse iterator"""
        for key in reversed(self._mapping):
            yield key

    def get(self, key: _KT, default=None, /):
        """Return the value for key if key is in the mapping, else default."""
        return self._mapping.get(key, default)

    def keys(self):
        """D.keys() -> a set-like object providing a view on D's keys"""
        return self._mapping.keys()

    def values(self):
        """D.values() -> an object providing a view on D's values"""
        return self._mapping.values()

    def items(self):
        """D.items() -> a set-like object providing a view on D's items"""
        return self._mapping.items()

    def copy(self) -> dict[_KT, _VT]:
        """D.copy() -> a shallow copy of D"""
        return self._mapping.copy()

    def __eq__(self, other) -> bool:
        # (mappingproxy_richcompare: the dict's comparison, which takes a mapping proxy's dict
        # for it; no other object is equal)
        if isinstance(other, mappingproxy):
            return self._mapping == other._mapping
        if isinstance(other, dict):
            return self._mapping == other
        return False

    def __ne__(self, other) -> bool:
        return not self == other

    def __hash__(self) -> int:
        # (mappingproxy_hash: the dict's hash, which raises)
        raise TypeError("unhashable type: 'dict'")

    def __or__(self, other):
        # (mappingproxy_or: the dicts' |, a new dict)
        if isinstance(other, mappingproxy):
            return self._mapping | other._mapping
        return self._mapping | other

    def __ror__(self, other: dict[_KT, _VT]) -> dict[_KT, _VT]:
        return other | self._mapping

    def __ior__(self, other) -> Self:
        raise TypeError("'|=' is not supported by mappingproxy; use '|' instead")

    def __str__(self) -> str:
        return str(self._mapping)

    def __repr__(self) -> str:
        return f"mappingproxy({self._mapping!r})"
