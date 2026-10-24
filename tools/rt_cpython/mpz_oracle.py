"""Independent CPython-int oracle for Pystachy's explicit mpz module.

The differential fixtures import this only when the native mpz module is absent.
There is deliberately no mpz.py here: that would shadow Pystachy's lib/mpz.py.
This is a testing twin, not an implementation of the packed-limb algorithms.
"""

__all__ = ["mpz"]


def _integer(value):
    if isinstance(value, mpz):
        return value._value
    if isinstance(value, int):
        return value
    raise TypeError("mpz arithmetic requires an mpz or int operand")


def _wrap(value):
    result = object.__new__(mpz)
    result._value = value
    return result


class mpz:
    __slots__ = ("_value",)

    def __init__(self, value=0, base=10):
        if hasattr(self, "_value"):
            return  # Immutable instances, like int, ignore repeated initialization.
        if isinstance(value, str):
            self._value = int(value, base)
        elif base != 10:
            raise TypeError("mpz() can't convert non-string with explicit base")
        elif isinstance(value, int):
            self._value = value
        else:
            raise TypeError("mpz constructor requires int or str")

    def __str__(self):
        return str(self._value)

    def __repr__(self):
        return str(self._value)

    def __bool__(self):
        return bool(self._value)

    def __hash__(self):
        return hash(self._value)

    def copy(self):
        return _wrap(self._value)

    def to_int(self):
        if not -(1 << 63) <= self._value < 1 << 63:
            raise OverflowError("mpz does not fit in signed 64-bit int")
        return self._value

    def bit_length(self):
        return self._value.bit_length()

    def abs(self):
        return _wrap(abs(self._value))

    def pow(self, exponent):
        if exponent < 0:
            raise ValueError("mpz exponent must be nonnegative")
        return _wrap(pow(self._value, exponent))

    def __neg__(self):
        return _wrap(-self._value)

    def __pos__(self):
        return self

    def __invert__(self):
        return _wrap(~self._value)

    def __add__(self, other):
        return _wrap(self._value + _integer(other))

    def __sub__(self, other):
        return _wrap(self._value - _integer(other))

    def __mul__(self, other):
        return _wrap(self._value * _integer(other))

    def __floordiv__(self, other):
        return _wrap(self._value // _integer(other))

    def __mod__(self, other):
        return _wrap(self._value % _integer(other))

    def __and__(self, other):
        return _wrap(self._value & _integer(other))

    def __or__(self, other):
        return _wrap(self._value | _integer(other))

    def __xor__(self, other):
        return _wrap(self._value ^ _integer(other))

    def __lshift__(self, count):
        return _wrap(self._value << count)

    def __rshift__(self, count):
        return _wrap(self._value >> count)

    def __eq__(self, other):
        if not isinstance(other, (mpz, int)):
            return False
        return self._value == _integer(other)

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        return self._value < _integer(other)

    def __le__(self, other):
        return self._value <= _integer(other)

    def __gt__(self, other):
        return self._value > _integer(other)

    def __ge__(self, other):
        return self._value >= _integer(other)
