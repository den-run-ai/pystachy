"""Experimental promoting integer value for the python-int source pragma.

The wrapper is always GC-scanned. _small is a full signed int64; _large is
None or an immutable mpz reference. No pointer is stored in an integer slot.
This is a correctness prototype, not the final unboxed/tagged representation.
"""
from mpz import mpz


class integer:
    # A concrete class, not a template: an opted-in int annotation names one static
    # type, so a recursive function's annotated result is known before it returns.
    # int(x) and int(text, base) construct through convert() and convert_base().
    def __init__(self, small: int = 0) -> None:
        self._small: int = small
        self._large: mpz | None = None

    def __init_subclass__(cls) -> None:
        raise TypeError("python-int prototype does not support int subclasses")

    def _big(self) -> mpz:
        big = self._large
        return mpz(self._small) if big is None else big

    def _index(self) -> int:
        big = self._large
        return self._small if big is None else big.to_int()

    def _bound(self) -> int:
        try:
            return self._index()
        except OverflowError:
            return -9223372036854775807 if self._big() < 0 else 9223372036854775807

    def _subscript(self) -> int:
        try:
            return self._index()
        except OverflowError:
            raise IndexError("cannot fit 'int' into an index-sized integer")

    def __str__(self) -> str:
        big = self._large
        return str(self._small) if big is None else str(big)

    def __repr__(self) -> str:
        return str(self)

    def __bool__(self) -> bool:
        big = self._large
        return self._small != 0 if big is None else bool(big)

    def __hash__(self) -> int:
        big = self._large
        return hash(self._small) if big is None else hash(big)

    def _binary(self, other, op: int, symbol: str) -> "integer":
        rhs = _operand(other, symbol, op < 5)
        if self._large is None and rhs._large is None:
            a = self._small
            b = rhs._small
            try:
                if op == 0:
                    return integer(a + b)
                if op == 1:
                    return integer(a - b)
                if op == 2:
                    return integer(a * b)
                if op == 3:
                    return integer(a // b)
                if op == 4:
                    return integer(a % b)
                if op == 5:
                    return integer(a & b)
                if op == 6:
                    return integer(a | b)
                return integer(a ^ b)
            except OverflowError:
                pass
        x = self._big()
        y = rhs._big()
        if op == 0:
            return _from_big(x + y)
        if op == 1:
            return _from_big(x - y)
        if op == 2:
            return _from_big(x * y)
        if op == 3:
            return _from_big(x // y)
        if op == 4:
            return _from_big(x % y)
        if op == 5:
            return _from_big(x & y)
        if op == 6:
            return _from_big(x | y)
        return _from_big(x ^ y)

    def __add__(self, other) -> "integer":
        return self._binary(other, 0, "+")

    def __sub__(self, other) -> "integer":
        return self._binary(other, 1, "-")

    def __mul__(self, other) -> "integer":
        return self._binary(other, 2, "*")

    def __floordiv__(self, other) -> "integer":
        return self._binary(other, 3, "//")

    def __mod__(self, other) -> "integer":
        return self._binary(other, 4, "%")

    def __and__(self, other) -> "integer":
        return self._binary(other, 5, "&")

    def __or__(self, other) -> "integer":
        return self._binary(other, 6, "|")

    def __xor__(self, other) -> "integer":
        return self._binary(other, 7, "^")

    def __neg__(self) -> "integer":
        if self._large is None:
            try:
                return integer(-self._small)
            except OverflowError:
                pass
        return _from_big(-self._big())

    def __pos__(self) -> "integer":
        return self

    def __abs__(self) -> "integer":
        return -self if self < 0 else self

    def __invert__(self) -> "integer":
        return integer(~self._small) if self._large is None else _from_big(~self._big())

    def _shift(self, count, right: bool) -> "integer":
        rhs = _operand(count, ">>" if right else "<<", False)
        if rhs < 0:
            raise ValueError("negative shift count")
        if not self:
            return self
        if rhs._large is not None:
            if right:
                return integer(-1 if self < 0 else 0)
            raise OverflowError("too many digits in integer")
        n = rhs._small
        if self._large is None:
            try:
                return integer(self._small >> n if right else self._small << n)
            except OverflowError:
                pass
        return _from_big(self._big() >> n if right else self._big() << n)

    def __lshift__(self, count) -> "integer":
        return self._shift(count, False)

    def __rshift__(self, count) -> "integer":
        return self._shift(count, True)

    def __pow__(self, exponent) -> "integer":
        n = _operand(exponent, "** or pow()", True)
        if n < 0:
            raise NotImplementedError("python-int prototype: negative non-modular power needs float integration")
        result = integer(1)
        base = self
        while n:
            if n & 1:
                result = result * base
            n = n >> 1
            if n:
                base = base * base
        return result

    def __divmod__(self, other: "integer") -> tuple["integer", "integer"]:
        return self // other, self % other

    def bit_length(self) -> "integer":
        return integer(self._big().bit_length())

    def bit_count(self) -> "integer":
        x = abs(self)
        total = integer(0)
        while x:
            x = x & (x - 1)
            total = total + 1
        return total

    def _compare(self, other, symbol: str) -> int:
        rhs = _ordering_operand(other, symbol)
        if self._large is None and rhs._large is None:
            return -1 if self._small < rhs._small else 1 if self._small > rhs._small else 0
        a = self._big()
        b = rhs._big()
        return -1 if a < b else 1 if a > b else 0

    def _identical(self, other: "integer") -> bool:
        # self is other for two distinct wrappers: CPython's answer where the values decide it
        # (unequal values, or equal ones in its small-int cache); else it depends on how CPython
        # made each object (a shared constant, or a fresh result)
        if self._compare(other, "is") != 0:
            return False
        if self._large is None and self._small >= -5 and self._small <= 256:
            return True
        raise NotImplementedError("python-int prototype: identity of equal integers outside CPython's small-int cache")

    def __eq__(self, other) -> bool:
        if isinstance(other, integer) or isinstance(other, int):
            return self._compare(other, "==") == 0
        # Never silently return False for a numeric case whose exact comparison
        # this prototype cannot yet implement.
        if isinstance(other, float):
            raise NotImplementedError("python-int prototype: mixed float comparison")
        return False

    def __ne__(self, other) -> bool:
        return not self == other

    def __lt__(self, other) -> bool:
        return self._compare(other, "<") < 0

    def __le__(self, other) -> bool:
        return self._compare(other, "<=") <= 0

    def __gt__(self, other) -> bool:
        return self._compare(other, ">") > 0

    def __ge__(self, other) -> bool:
        return self._compare(other, ">=") >= 0


def _from_big(value: mpz) -> integer:
    result = integer()
    try:
        result._small = value.to_int()
    except OverflowError:
        result._large = value
    return result


def power(base, exponent, modulus=None) -> integer:
    a = operand(base)
    b = operand(exponent)
    if modulus is None:
        return a ** b
    m = operand(modulus)
    if not m:
        raise ValueError("pow() 3rd argument cannot be 0")
    if b < 0:
        # Extended Euclid; retain CPython's negative-modulus remainder rule.
        old_r = a % m
        r = m
        old_s = integer(1)
        s = integer(0)
        while r:
            q = old_r // r
            old_r, r = r, old_r - q * r
            old_s, s = s, old_s - q * s
        if abs(old_r) != 1:
            raise ValueError("base is not invertible for the given modulus")
        a = (old_s if old_r > 0 else -old_s) % m
        b = -b
    result = integer(1) % m
    a = a % m
    while b:
        if b & 1:
            result = result * a % m
        b = b >> 1
        if b:
            a = a * a % m
    return result


def radix(value, base: int, prefix: str) -> str:
    x = _index_operand(value)
    negative = x < 0
    x = abs(x)
    out: list[str] = []
    if not x:
        out.append("0")
    while x:
        out.append("0123456789abcdef"[(x % base)._index()])
        x = x // base
    out.reverse()
    return ("-" if negative else "") + prefix + "".join(out)


def binary(value) -> str:
    return radix(value, 2, "0b")


def octal(value) -> str:
    return radix(value, 8, "0o")


def hexadecimal(value) -> str:
    return radix(value, 16, "0x")


class integer_range:
    def __init__(self, start, stop=None, step=1) -> None:
        self.start = integer(0) if stop is None else _index_operand(start)
        self.stop = _index_operand(start) if stop is None else _index_operand(stop)
        self.step = _index_operand(step)
        if not self.step:
            raise ValueError("range() arg 3 must not be zero")

    def __iter__(self):
        value = self.start
        if self.step > 0:
            while value < self.stop:
                yield value
                value = value + self.step
        else:
            while value > self.stop:
                yield value
                value = value + self.step


def _parse(text: str, radix: int) -> integer:
    try:
        return integer(int(text, radix))
    except OverflowError:
        result = integer()
        result._large = mpz(text, radix)
        return result


def convert(value=0) -> integer:
    # int(value): an already-promoted value keeps its identity
    if isinstance(value, integer):
        return value
    if isinstance(value, str):
        return _parse(value, 10)
    if isinstance(value, int):
        return integer(int(value))
    raise TypeError("python-int prototype requires an integer or string")


def is_integer(value) -> bool:
    return isinstance(value, integer) or isinstance(value, int)


def integer_sum(values, start=0) -> integer:
    result = operand(start)
    for value in values:
        result = result + value
    return result


def convert_base(value, base) -> integer:
    # int(value, base) and an exact literal past int64; CPython checks the base first
    if base is None:
        raise TypeError("'NoneType' object cannot be interpreted as an integer")
    radix = int(base) if isinstance(base, int) else _index_operand(base)._bound()
    if radix != 0 and (radix < 2 or radix > 36):
        raise ValueError("int() base must be >= 2 and <= 36, or 0")
    if not isinstance(value, str):
        raise TypeError("int() can't convert non-string with explicit base")
    return _parse(value, radix)


def operand(value) -> integer:
    # Numeric operations never parse text, unlike construction.
    if isinstance(value, integer):
        return value
    if isinstance(value, int):
        return integer(int(value))
    raise TypeError("python-int operation requires an integer")


def _operand(value, symbol: str, arithmetic: bool) -> integer:
    # CPython's TypeError for a right operand that int has no operation with.
    # Float arithmetic, which CPython performs, is unimplemented, not an error.
    if isinstance(value, integer):
        return value
    if isinstance(value, int):
        return integer(int(value))
    if arithmetic and isinstance(value, float):
        raise NotImplementedError("python-int prototype: mixed float arithmetic")
    raise TypeError("unsupported operand type(s) for " + symbol + ": 'int' and '" + type(value).__name__ + "'")


def _ordering_operand(value, symbol: str) -> integer:
    if isinstance(value, integer):
        return value
    if isinstance(value, int):
        return integer(int(value))
    if isinstance(value, float):
        raise NotImplementedError("python-int prototype: mixed float comparison")
    raise TypeError("'" + symbol + "' not supported between instances of 'int' and '" + type(value).__name__ + "'")


def _index_operand(value) -> integer:
    # range() arguments, int() bases and bin/oct/hex values: CPython's __index__ error
    if isinstance(value, integer):
        return value
    if isinstance(value, int):
        return integer(int(value))
    raise TypeError("'" + type(value).__name__ + "' object cannot be interpreted as an integer")
