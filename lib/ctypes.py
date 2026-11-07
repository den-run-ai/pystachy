"""Experimental static ctypes declarations; see docs/ffi.md.

The loader lowers literal CDLL/argtypes/restype blocks to ffi.extern. This
module supplies only the actual pointer cells and helpers used by those calls.
"""
from _pystachy_ctypes import bytes_at as _bytes_at
from typing import Any

_Int = int
_Float = float
_Bytes = bytes | None
_Address = int | bool | None


class c_void_p:
    """A pointer-sized output cell with an explicit lifetime."""

    def __init__(self, value: _Address = None):
        self._storage: list[int] = [_address(value)]

    def __bool__(self) -> bool:
        return self.value is not None

    @property
    def value(self) -> int | None:
        return _pointer_value(self._storage[0])

    @value.setter
    def value(self, value: _Address) -> None:
        self._storage[0] = _address(value)


class _Pointer:
    def __init__(self, cell: c_void_p):
        self._cell = cell


def byref(value: c_void_p) -> _Pointer:
    """Borrow a c_void_p cell during a POINTER(c_void_p) call."""
    return _Pointer(value)


def _byref_cell(value: c_void_p) -> c_void_p:
    # The declaration lowerer uses this only for an immediately consumed byref.
    # Keep its parameter check and evaluation point without allocating a wrapper.
    return value


def string_at(address: Any, size: int = -1) -> bytes:
    """Copy native bytes; -1 reads through the first NUL."""
    return _bytes_at(_address(address), size)


def _address(value: Any) -> int:
    checked = __pys_ctypes_value(value, "address")
    if checked is None:
        return 0
    if checked < 0:
        raise OverflowError("ctypes pointers require an address below 2**63")
    return int(checked)


def _pointer_value(value: int) -> int | None:
    value = _address(value)
    return None if value == 0 else value


def _borrow(value: Any) -> list[int]:
    cell = __pys_ctypes_value(value, "cell")
    if len(cell._storage) != 1:
        raise ValueError("ctypes pointer cells require exactly one storage slot")
    return cell._storage


def _signed32(value: Any) -> int:
    narrowed = int(__pys_ctypes_value(value, "integer")) & 4294967295
    return narrowed - 4294967296 if narrowed >= 2147483648 else narrowed


def _unsigned32(value: Any) -> int:
    return int(__pys_ctypes_value(value, "integer")) & 4294967295


def _integer(value: Any) -> int:
    return int(__pys_ctypes_value(value, "integer"))


def _floating(value: Any) -> float:
    return float(__pys_ctypes_value(value, "number"))
