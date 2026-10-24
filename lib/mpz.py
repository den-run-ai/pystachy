"""Explicit immutable arbitrary-precision integers, backed by the native runtime.

Ordinary Pystachy int remains checked signed 64-bit. Construct mpz from an int
or a string, and keep calculations in mpz to grow beyond that range. The
CPython reference module in tools/rt_cpython delegates arithmetic to int.
"""

__all__ = ["mpz"]


class mpz:
    def __init__(self, value: int | str | bool = 0, base: int = 10) -> None:
        if isinstance(value, str):
            self._handle = __pys_mpz_from_str(value, base)
        elif base != 10:
            raise TypeError("mpz() can't convert non-string with explicit base")
        elif isinstance(value, bool):
            self._handle = __pys_mpz_from_int(1 if value else 0)
        else:
            self._handle = __pys_mpz_from_int(value)

    def __init_subclass__(cls) -> None:
        raise TypeError("type 'mpz' is not an acceptable base type")

    def __str__(self) -> str:
        return __pys_mpz_str(self._handle)

    def __repr__(self) -> str:
        return __pys_mpz_str(self._handle)

    def __bool__(self) -> bool:
        return __pys_mpz_bit_length(self._handle) != 0

    def __hash__(self) -> int:
        return __pys_mpz_hash(self._handle)

    def copy(self) -> "mpz":
        return _wrap(self._handle)

    def to_int(self) -> int:
        """Return a checked signed 64-bit int; raise OverflowError if too large."""
        return __pys_mpz_to_int(self._handle)

    def bit_length(self) -> int:
        return __pys_mpz_bit_length(self._handle)

    def abs(self) -> "mpz":
        return _wrap(__pys_mpz_unary(self._handle, 1))

    def pow(self, exponent: int) -> "mpz":
        """Integer power with a nonnegative signed 64-bit exponent."""
        return _wrap(__pys_mpz_pow(self._handle, exponent))

    def __neg__(self) -> "mpz":
        return _wrap(__pys_mpz_unary(self._handle, 0))

    def __pos__(self) -> "mpz":
        return self

    def __invert__(self) -> "mpz":
        return _wrap(__pys_mpz_unary(self._handle, 2))

    def __add__(self, other) -> "mpz":
        return _wrap(__pys_mpz_binop(self._handle, _handle_of(other), 0))

    def __sub__(self, other) -> "mpz":
        return _wrap(__pys_mpz_binop(self._handle, _handle_of(other), 1))

    def __mul__(self, other) -> "mpz":
        return _wrap(__pys_mpz_binop(self._handle, _handle_of(other), 2))

    def __floordiv__(self, other) -> "mpz":
        return _wrap(__pys_mpz_binop(self._handle, _handle_of(other), 3))

    def __mod__(self, other) -> "mpz":
        return _wrap(__pys_mpz_binop(self._handle, _handle_of(other), 4))

    def __and__(self, other) -> "mpz":
        return _wrap(__pys_mpz_binop(self._handle, _handle_of(other), 5))

    def __or__(self, other) -> "mpz":
        return _wrap(__pys_mpz_binop(self._handle, _handle_of(other), 6))

    def __xor__(self, other) -> "mpz":
        return _wrap(__pys_mpz_binop(self._handle, _handle_of(other), 7))

    def __lshift__(self, count: int) -> "mpz":
        return _wrap(__pys_mpz_shift(self._handle, count, 0))

    def __rshift__(self, count: int) -> "mpz":
        return _wrap(__pys_mpz_shift(self._handle, count, 1))

    def __eq__(self, other) -> bool:
        if isinstance(other, mpz) or isinstance(other, int):
            return __pys_mpz_cmp(self._handle, _handle_of(other)) == 0
        return False

    def __ne__(self, other) -> bool:
        return not self == other

    def __lt__(self, other) -> bool:
        return __pys_mpz_cmp(self._handle, _handle_of(other)) < 0

    def __le__(self, other) -> bool:
        return __pys_mpz_cmp(self._handle, _handle_of(other)) <= 0

    def __gt__(self, other) -> bool:
        return __pys_mpz_cmp(self._handle, _handle_of(other)) > 0

    def __ge__(self, other) -> bool:
        return __pys_mpz_cmp(self._handle, _handle_of(other)) >= 0


def _wrap(handle) -> mpz:
    # The opaque handle's inferred type cannot be spelled by ordinary Python.
    # No published payload is mutated: this initializes a fresh wrapper only.
    result = mpz()
    result._handle = handle
    return result


def _handle_of(value):
    if isinstance(value, mpz):
        return value._handle
    if isinstance(value, int):
        return __pys_mpz_from_int(int(value))
    raise TypeError("mpz arithmetic requires an mpz or int operand")
