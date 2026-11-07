"""Experimental static ctypes declarations; see docs/ffi.md.

The loader lowers literal CDLL/argtypes/restype blocks to ffi.extern. This
module supplies only the actual pointer cells and helpers used by those calls.
"""
from _pystachy_ctypes import bytes_at as _bytes_at

_Int = int
_Float = float
_Bytes = bytes | None
_Integer = int | bool
_Number = int | float | bool
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


def string_at(address: int | None, size: int = -1) -> bytes:
    """Copy native bytes; -1 reads through the first NUL."""
    return _bytes_at(_address(address), size)


def _address(value: _Address) -> int:
    if value is None:
        return 0
    if value < 0:
        raise OverflowError("ctypes pointers require an address below 2**63")
    return int(value)


def _pointer_value(value: int) -> int | None:
    value = _address(value)
    return None if value == 0 else value


def _borrow(value: _Pointer) -> list[int]:
    if len(value._cell._storage) != 1:
        raise ValueError("ctypes pointer cells require exactly one storage slot")
    return value._cell._storage


def _signed32(value: _Integer) -> int:
    narrowed = int(value) & 4294967295
    return narrowed - 4294967296 if narrowed >= 2147483648 else narrowed


def _unsigned32(value: _Integer) -> int:
    return int(value) & 4294967295


def _integer(value: _Integer) -> int:
    return int(value)


def _floating(value: _Number) -> float:
    return float(value)
