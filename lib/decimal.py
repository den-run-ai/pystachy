# pystachy: python-int
"""Decimal fixed-point and floating-point arithmetic.

A subset of CPython's decimal module, written for Pystachy: the Decimal type with exact
construction, context-rounded arithmetic, comparison, hashing, quantizing, rounding, square
roots and formatting, and the contexts that set precision and rounding. The arithmetic follows
the General Decimal Arithmetic Specification as CPython's Lib/_pydecimal.py implements it, on
integer coefficients; integer powers are computed as CPython's C implementation (libmpdec)
computes them, and exceptions carry its messages.

Not provided: signal flags and configurable traps (InvalidOperation, DivisionByZero and
Overflow always raise; the other signals never do), exp(), ln(), log10(), non-integer powers,
the logical and shifting operations, and construction from a Decimal or a tuple.
"""
import math
from typing import NamedTuple

__all__ = [
    "Decimal", "Context", "DecimalTuple", "DefaultContext", "BasicContext", "ExtendedContext",
    "DecimalException", "Clamped", "InvalidOperation", "DivisionByZero", "Inexact", "Rounded",
    "Subnormal", "Overflow", "Underflow", "FloatOperation", "DivisionImpossible", "InvalidContext",
    "ConversionSyntax", "DivisionUndefined", "ROUND_DOWN", "ROUND_HALF_UP", "ROUND_HALF_EVEN",
    "ROUND_CEILING", "ROUND_FLOOR", "ROUND_UP", "ROUND_HALF_DOWN", "ROUND_05UP", "setcontext",
    "getcontext", "localcontext", "MAX_PREC", "MAX_EMAX", "MIN_EMIN", "MIN_ETINY", "HAVE_THREADS",
    "HAVE_CONTEXTVAR",
]

__version__ = "1.70"
__libmpdec_version__ = "2.4.2"

ROUND_DOWN = "ROUND_DOWN"
ROUND_HALF_UP = "ROUND_HALF_UP"
ROUND_HALF_EVEN = "ROUND_HALF_EVEN"
ROUND_CEILING = "ROUND_CEILING"
ROUND_FLOOR = "ROUND_FLOOR"
ROUND_UP = "ROUND_UP"
ROUND_HALF_DOWN = "ROUND_HALF_DOWN"
ROUND_05UP = "ROUND_05UP"

HAVE_THREADS = True
HAVE_CONTEXTVAR = True
MAX_PREC = 999999999999999999
MAX_EMAX = 999999999999999999
MIN_EMIN = -999999999999999999
MIN_ETINY = MIN_EMIN - (MAX_PREC - 1)

_ROUNDINGS = (ROUND_CEILING, ROUND_FLOOR, ROUND_UP, ROUND_DOWN, ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_05UP)
_HASH_MODULUS = 2305843009213693951  # 2**61 - 1, as sys.hash_info.modulus
_HASH_INF = 314159
_HASH_10INV = pow(10, _HASH_MODULUS - 2, _HASH_MODULUS)
_FINITE = 0
_INFINITY = 1
_NAN = 2
_SNAN = 3


class DecimalException(ArithmeticError):
    """Base exception class of the module's signals."""


class Clamped(DecimalException):
    """Exponent of a 0 changed to fit bounds."""


class InvalidOperation(DecimalException):
    """An invalid operation was performed."""


class ConversionSyntax(InvalidOperation):
    """Trying to convert a badly formed string."""


# CPython's DivisionByZero is a DecimalException too: a class here has one exception base, and
# ZeroDivisionError is the one that programs catch.
class DivisionByZero(ZeroDivisionError):
    """Division by 0."""


class DivisionImpossible(InvalidOperation):
    """Cannot perform the division adequately."""


class DivisionUndefined(InvalidOperation):
    """Undefined result of division."""


class Inexact(DecimalException):
    """Had to round, losing information."""


class InvalidContext(InvalidOperation):
    """Invalid context. Unknown rounding, for example."""


class Rounded(DecimalException):
    """Number got rounded (not necessarily changed during rounding)."""


class Subnormal(DecimalException):
    """Exponent < Emin before rounding."""


class Overflow(Inexact):
    """Numerical overflow."""


class Underflow(Inexact):
    """Numerical underflow with result rounded to 0."""


class FloatOperation(DecimalException):
    """Enable stricter semantics for mixing floats and Decimals."""


class DecimalTuple(NamedTuple):
    sign: int
    digits: tuple[int, ...]
    exponent: int | str


class Context:
    """The precision, rounding and exponent limits that arithmetic rounds its results to."""

    def __init__(self, prec: int | None = None, rounding: str | None = None, Emin: int | None = None,
                 Emax: int | None = None, capitals: int | None = None, clamp: int | None = None) -> None:
        self._prec: int = 28
        self._rounding: str = ROUND_HALF_EVEN
        self._emin: int = -999999
        self._emax: int = 999999
        self._capitals: int = 1
        self._clamp: int = 0
        template = _template
        if template is not None:
            # DefaultContext is the prototype of new contexts: what a program sets on it is
            # the default of the fields left out here (but capitals, which is 1)
            self._prec = template._prec
            self._rounding = template._rounding
            self._emin = template._emin
            self._emax = template._emax
            self._clamp = template._clamp
        if prec is not None:
            self.prec = prec
        if rounding is not None:
            self.rounding = rounding
        if Emin is not None:
            self.Emin = Emin
        if Emax is not None:
            self.Emax = Emax
        if capitals is not None:
            self.capitals = capitals
        if clamp is not None:
            self.clamp = clamp

    @property
    def prec(self) -> int:
        return self._prec

    @prec.setter
    def prec(self, value: int) -> None:
        if value < 1 or value > MAX_PREC:
            raise ValueError("valid range for prec is [1, MAX_PREC]")
        self._prec = value

    @property
    def rounding(self) -> str:
        return self._rounding

    @rounding.setter
    def rounding(self, value: str) -> None:
        if value not in _ROUNDINGS:
            raise TypeError("valid values for rounding are:\n  [ROUND_CEILING, ROUND_FLOOR, ROUND_UP, ROUND_DOWN,\n   ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN,\n   ROUND_05UP]")
        self._rounding = value

    @property
    def Emin(self) -> int:
        return self._emin

    @Emin.setter
    def Emin(self, value: int) -> None:
        if value > 0 or value < MIN_EMIN:
            raise ValueError("valid range for Emin is [MIN_EMIN, 0]")
        self._emin = value

    @property
    def Emax(self) -> int:
        return self._emax

    @Emax.setter
    def Emax(self, value: int) -> None:
        if value < 0 or value > MAX_EMAX:
            raise ValueError("valid range for Emax is [0, MAX_EMAX]")
        self._emax = value

    @property
    def capitals(self) -> int:
        return self._capitals

    @capitals.setter
    def capitals(self, value: int) -> None:
        if value != 0 and value != 1:
            raise ValueError("valid values for capitals are 0 or 1")
        self._capitals = value

    @property
    def clamp(self) -> int:
        return self._clamp

    @clamp.setter
    def clamp(self, value: int) -> None:
        if value != 0 and value != 1:
            raise ValueError("valid values for clamp are 0 or 1")
        self._clamp = value

    def __repr__(self) -> str:
        return (f"Context(prec={self._prec}, rounding={self._rounding}, Emin={self._emin}, Emax={self._emax}, "
                f"capitals={self._capitals}, clamp={self._clamp}, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow])")

    def copy(self) -> "Context":
        return Context(self._prec, self._rounding, self._emin, self._emax, self._capitals, self._clamp)

    def __copy__(self) -> "Context":
        return self.copy()

    def clear_flags(self) -> None:
        """Signal flags are not recorded: nothing to clear."""

    def clear_traps(self) -> None:
        raise NotImplementedError("the traps of a decimal context are fixed in Pystachy")

    def Etiny(self) -> int:
        return self._emin - self._prec + 1

    def Etop(self) -> int:
        return self._emax - self._prec + 1

    def create_decimal(self, num: str | int | float = "0") -> "Decimal":
        """A Decimal from num, rounded to this context (unlike the Decimal constructor)."""
        if isinstance(num, str) and (num != num.strip() or "_" in num):
            # (text as the specification writes a number: the constructor's surrounding
            # whitespace and underscores are not part of it)
            raise InvalidOperation("[<class 'decimal.ConversionSyntax'>]")
        d = Decimal(num, self)
        if d._kind >= _NAN and _ndigits(d._int) > self._prec - self._clamp and d._int != 0:
            raise InvalidOperation("[<class 'decimal.ConversionSyntax'>]")
        return d._fix(self)

    def create_decimal_from_float(self, f: float) -> "Decimal":
        return Decimal(f)._fix(self)

    def abs(self, a: "Decimal") -> "Decimal":
        return a.copy_abs()._fix(self) if a._kind < _NAN else a._unary(self, 0)

    def add(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a._add(b, self)

    def subtract(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a._add(b.copy_negate() if b._kind < _NAN else b, self)

    def multiply(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a._mul(b, self)

    def divide(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a._div(b, self)

    def divide_int(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a._floordiv(b, self)

    def remainder(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a._mod(b, self)

    def divmod(self, a: "Decimal", b: "Decimal") -> "tuple[Decimal, Decimal]":
        return a._divmod(b, self)

    def power(self, a: "Decimal", b: int) -> "Decimal":
        return a._pow(b, self)

    def sqrt(self, a: "Decimal") -> "Decimal":
        return a.sqrt(self)

    def quantize(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a.quantize(b, None, self)

    def normalize(self, a: "Decimal") -> "Decimal":
        return a.normalize(self)

    def plus(self, a: "Decimal") -> "Decimal":
        return a._unary(self, 0)

    def minus(self, a: "Decimal") -> "Decimal":
        return a._unary(self, 1)

    def to_integral_value(self, a: "Decimal") -> "Decimal":
        return a.to_integral_value(None, self)

    def to_integral_exact(self, a: "Decimal") -> "Decimal":
        return a.to_integral_exact(None, self)

    def to_integral(self, a: "Decimal") -> "Decimal":
        return a.to_integral_value(None, self)

    def compare(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a.compare(b, self)

    def max(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a.max(b, self)

    def min(self, a: "Decimal", b: "Decimal") -> "Decimal":
        return a.min(b, self)

    def to_sci_string(self, a: "Decimal") -> str:
        return a._text(False, self)

    def to_eng_string(self, a: "Decimal") -> str:
        return a._text(True, self)

    def is_finite(self, a: "Decimal") -> bool:
        return a.is_finite()

    def is_infinite(self, a: "Decimal") -> bool:
        return a.is_infinite()

    def is_nan(self, a: "Decimal") -> bool:
        return a.is_nan()

    def is_zero(self, a: "Decimal") -> bool:
        return a.is_zero()

    def is_signed(self, a: "Decimal") -> bool:
        return a.is_signed()

    def is_normal(self, a: "Decimal") -> bool:
        return a.is_normal(self)

    def is_subnormal(self, a: "Decimal") -> bool:
        return a.is_subnormal(self)


class _ContextManager:
    """localcontext()'s context manager: a copy of a context, current inside the with block."""

    def __init__(self, new_context: Context) -> None:
        self.new_context = new_context
        self.saved_context = new_context

    def __enter__(self) -> Context:
        global _current
        self.saved_context = getcontext()
        _current = self.new_context
        return self.new_context

    def __exit__(self, t, v, tb) -> None:
        global _current
        _current = self.saved_context


_template: Context | None = None  # DefaultContext, once it is made
_current: Context | None = None  # the current context: a copy of DefaultContext at its first use


def getcontext() -> Context:
    """The current context, which arithmetic operators round to."""
    global _current
    context = _current
    if context is None:
        context = DefaultContext.copy()
        _current = context
    return context


def setcontext(context: Context) -> None:
    """Make context the current one (a copy of it, for the three contexts the module predefines)."""
    global _current
    if context is DefaultContext or context is BasicContext or context is ExtendedContext:
        context = context.copy()
    _current = context


def localcontext(ctx: Context | None = None, *, prec: int | None = None, rounding: str | None = None,
                 Emin: int | None = None, Emax: int | None = None, capitals: int | None = None,
                 clamp: int | None = None) -> _ContextManager:
    """A context manager whose block runs with a copy of ctx (the current context by default)."""
    new = (getcontext() if ctx is None else ctx).copy()
    if prec is not None:
        new.prec = prec
    if rounding is not None:
        new.rounding = rounding
    if Emin is not None:
        new.Emin = Emin
    if Emax is not None:
        new.Emax = Emax
    if capitals is not None:
        new.capitals = capitals
    if clamp is not None:
        new.clamp = clamp
    return _ContextManager(new)


def _ndigits(n: int) -> int:
    # the number of decimal digits of n >= 0 (1 for 0), without the text of a large n
    if n < 10:
        return 1
    d = n.bit_length() * 1233 >> 12
    while n >= 10 ** d:
        d += 1
    while n < 10 ** (d - 1):
        d -= 1
    return d


def _round_changed(sign: int, q: int, r: int, half: int, keep: int, rounding: str) -> int:
    # which way rounding moves a coefficient cut into quotient q and remainder r (half is half a
    # unit of q's last place; keep is the number of digits q keeps): 1 up, 0 exact, -1 down
    down = 0 if r == 0 else -1
    if rounding == ROUND_HALF_EVEN:
        if r == half and (keep == 0 or q % 2 == 0):
            return -1
        return 1 if r >= half else down
    if rounding == ROUND_HALF_UP:
        return 1 if r >= half else down
    if rounding == ROUND_DOWN:
        return down
    if rounding == ROUND_UP:
        return -down
    if rounding == ROUND_HALF_DOWN:
        if r == half:
            return -1
        return 1 if r >= half else down
    if rounding == ROUND_CEILING:
        return down if sign else -down
    if rounding == ROUND_FLOOR:
        return -down if sign else down
    if rounding == ROUND_05UP:
        if keep and q % 10 != 0 and q % 10 != 5:
            return down
        return -down
    raise TypeError("invalid rounding mode")


def _signed_text(n: int) -> str:
    return ("+" if n >= 0 else "-") + str(abs(n))


def _parse_error() -> InvalidOperation:
    return InvalidOperation("[<class 'decimal.ConversionSyntax'>]")


class Decimal:
    """A decimal floating-point number: (-1)**sign * coefficient * 10**exponent, or a special value."""

    __slots__ = ("_sign", "_int", "_exp", "_kind")

    def __init__(self, value: str | int | float = "0", context: Context | None = None) -> None:
        self._sign: int = 0
        self._int: int = 0  # the coefficient; a NaN's diagnostic digits
        self._exp: int = 0
        self._kind: int = _FINITE
        if isinstance(value, int):
            if value < 0:
                self._sign = 1
                self._int = -value
            else:
                self._int = value
        elif isinstance(value, float):
            if math.isnan(value):
                self._kind = _NAN
                self._sign = 1 if math.copysign(1.0, value) < 0.0 else 0
            elif math.isinf(value):
                self._kind = _INFINITY
                self._sign = 1 if value < 0.0 else 0
            else:
                self._sign = 1 if math.copysign(1.0, value) < 0.0 else 0
                mantissa, e = math.frexp(abs(value))
                n = int(mantissa * 9007199254740992.0)  # abs(value) is n * 2**(e - 53), exactly
                k = 53 - e
                while k > 0 and n % 2 == 0:
                    n //= 2
                    k -= 1
                if k <= 0:
                    self._int = n * 2 ** -k
                else:
                    self._int = n * 5 ** k  # n / 2**k is n * 5**k / 10**k
                    self._exp = -k
        else:
            self._parse(value)

    def _parse(self, value: str) -> None:
        # [sign] (digits [. digits] | . digits) [E [sign] digits] | [sign] Inf[inity] | [sign] [s]NaN [digits]
        text = value.strip().replace("_", "")
        i = 0
        n = len(text)
        if i < n and (text[i] == "-" or text[i] == "+"):
            self._sign = 1 if text[i] == "-" else 0
            i += 1
        rest = text[i:].lower()
        if rest == "inf" or rest == "infinity":
            self._kind = _INFINITY
            return
        if rest.startswith("nan") or rest.startswith("snan"):
            diag = rest[3:] if rest.startswith("nan") else rest[4:]
            if diag != "" and not diag.isdecimal():
                raise _parse_error()
            self._kind = _NAN if rest.startswith("nan") else _SNAN
            self._int = int(diag) if diag != "" else 0
            return
        start = i
        while i < n and text[i].isdecimal():
            i += 1
        intpart = text[start:i]
        fracpart = ""
        if i < n and text[i] == ".":
            i += 1
            start = i
            while i < n and text[i].isdecimal():
                i += 1
            fracpart = text[start:i]
        if intpart == "" and fracpart == "":
            raise _parse_error()
        exp = 0
        if i < n and (text[i] == "e" or text[i] == "E"):
            i += 1
            start = i
            if i < n and (text[i] == "-" or text[i] == "+"):
                i += 1
            digits = i
            while i < n and text[i].isdecimal():
                i += 1
            if i == digits:
                raise _parse_error()
            exp = int(text[start:i])
        if i != n:
            raise _parse_error()
        self._int = int(intpart + fracpart)
        self._exp = exp - len(fracpart)

    @classmethod
    def from_float(cls, f: float | int) -> "Decimal":
        """The exact value of a float (or an int)."""
        return Decimal(f)

    # ---- inspection

    def _isnan(self) -> bool:
        return self._kind >= _NAN

    def is_nan(self) -> bool:
        return self._kind >= _NAN

    def is_qnan(self) -> bool:
        return self._kind == _NAN

    def is_snan(self) -> bool:
        return self._kind == _SNAN

    def is_infinite(self) -> bool:
        return self._kind == _INFINITY

    def is_finite(self) -> bool:
        return self._kind == _FINITE

    def is_zero(self) -> bool:
        return self._kind == _FINITE and self._int == 0

    def is_signed(self) -> bool:
        return self._sign == 1

    def is_canonical(self) -> bool:
        return True

    def is_normal(self, context: Context | None = None) -> bool:
        if self._kind != _FINITE or self._int == 0:
            return False
        ctx = getcontext() if context is None else context
        return ctx._emin <= self.adjusted()

    def is_subnormal(self, context: Context | None = None) -> bool:
        if self._kind != _FINITE or self._int == 0:
            return False
        ctx = getcontext() if context is None else context
        return self.adjusted() < ctx._emin

    def adjusted(self) -> int:
        """The exponent of the most significant digit: 0 for a special value."""
        if self._kind != _FINITE:
            return 0
        return self._exp + _ndigits(self._int) - 1

    def as_tuple(self) -> DecimalTuple:
        digits = tuple([int(c) for c in str(self._int)]) if self._kind == _FINITE or self._int != 0 else ()
        if self._kind == _FINITE:
            return DecimalTuple(self._sign, digits, self._exp)
        return DecimalTuple(self._sign, (0,) if self._kind == _INFINITY else digits, "F" if self._kind == _INFINITY else "n" if self._kind == _NAN else "N")

    def as_integer_ratio(self) -> tuple[int, int]:
        if self._kind != _FINITE:
            if self._kind >= _NAN:
                raise ValueError("cannot convert NaN to integer ratio")
            raise OverflowError("cannot convert Infinity to integer ratio")
        if self._int == 0:
            return 0, 1
        n = self._int
        if self._exp >= 0:
            return (-n if self._sign else n) * 10 ** self._exp, 1
        d = 10 ** -self._exp
        g, rest = n, d
        while rest != 0:  # (math.gcd() takes 64-bit ints)
            g, rest = rest, g % rest
        return (-n if self._sign else n) // g, d // g

    def canonical(self) -> "Decimal":
        return self

    def conjugate(self) -> "Decimal":
        return self

    @property
    def real(self) -> "Decimal":
        return self

    @property
    def imag(self) -> "Decimal":
        return _dec(0, 0, 0)

    def radix(self) -> "Decimal":
        return _dec(0, 10, 0)

    def number_class(self, context: Context | None = None) -> str:
        if self._kind == _SNAN:
            return "sNaN"
        if self._kind == _NAN:
            return "NaN"
        if self._kind == _INFINITY:
            return "-Infinity" if self._sign else "+Infinity"
        if self._int == 0:
            return "-Zero" if self._sign else "+Zero"
        if self.is_subnormal(context):
            return "-Subnormal" if self._sign else "+Subnormal"
        return "-Normal" if self._sign else "+Normal"

    def same_quantum(self, other: "Decimal") -> bool:
        if self._kind != _FINITE or other._kind != _FINITE:
            return (self._kind >= _NAN and other._kind >= _NAN) or (self._kind == _INFINITY and other._kind == _INFINITY)
        return self._exp == other._exp

    def copy_abs(self) -> "Decimal":
        return _dec(0, self._int, self._exp, self._kind)

    def copy_negate(self) -> "Decimal":
        return _dec(1 - self._sign, self._int, self._exp, self._kind)

    def copy_sign(self, other: "Decimal") -> "Decimal":
        return _dec(other._sign, self._int, self._exp, self._kind)

    def __copy__(self) -> "Decimal":
        return self

    def __deepcopy__(self, memo) -> "Decimal":
        return self

    # ---- rounding to a context

    def _fix_nan(self, context: Context) -> "Decimal":
        # a NaN whose diagnostic digits fit the precision
        limit = context._prec - context._clamp
        if self._int != 0 and _ndigits(self._int) > limit:
            return _dec(self._sign, self._int % 10 ** limit, 0, self._kind)
        return self

    def _check_nans(self, other: "Decimal | None", context: Context) -> "Decimal | None":
        # the NaN that an operation on a NaN returns: a signaling one is an invalid operation
        if self._kind == _SNAN or (other is not None and other._kind == _SNAN):
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        if self._kind == _NAN:
            return self._fix_nan(context)
        if other is not None and other._kind == _NAN:
            return other._fix_nan(context)
        return None

    def _fix(self, context: Context) -> "Decimal":
        # round to the context's precision, within its exponent limits
        if self._kind != _FINITE:
            return self._fix_nan(context) if self._kind >= _NAN else self
        etiny = context._emin - context._prec + 1
        etop = context._emax - context._prec + 1
        if self._int == 0:
            exp_max = etop if context._clamp else context._emax
            new_exp = min(max(self._exp, etiny), exp_max)
            return self if new_exp == self._exp else _dec(self._sign, 0, new_exp)
        n = _ndigits(self._int)
        exp_min = n + self._exp - context._prec
        if exp_min > etop:
            raise Overflow("[<class 'decimal.Overflow'>]")
        if exp_min < etiny:
            exp_min = etiny  # (a subnormal result)
        if self._exp < exp_min:
            keep = n + self._exp - exp_min
            coeff = self._int
            if keep < 0:
                coeff = 1  # (less than half a unit in the last place: as 1E(exp_min-1) rounds)
                n = 1
                keep = 0
            unit = 10 ** (n - keep)
            q = coeff // unit
            if _round_changed(self._sign, q, coeff % unit, unit // 2, keep, context._rounding) > 0:
                q += 1
                if _ndigits(q) > context._prec:
                    q //= 10
                    exp_min += 1
            if exp_min > etop:
                raise Overflow("[<class 'decimal.Overflow'>]")
            return _dec(self._sign, q, exp_min)
        if context._clamp == 1 and self._exp > etop:
            return _dec(self._sign, self._int * 10 ** (self._exp - etop), etop)
        return self

    def _rescale(self, exp: int, rounding: str) -> "Decimal":
        # the value with exponent exp, rounded if digits are lost (no precision limit)
        if self._kind != _FINITE:
            return self
        if self._int == 0:
            return _dec(self._sign, 0, exp)
        if self._exp >= exp:
            return _dec(self._sign, self._int * 10 ** (self._exp - exp), exp)
        n = _ndigits(self._int)
        keep = n + self._exp - exp
        coeff = self._int
        if keep < 0:
            coeff = 1
            n = 1
            keep = 0
        unit = 10 ** (n - keep)
        q = coeff // unit
        if _round_changed(self._sign, q, coeff % unit, unit // 2, keep, rounding) == 1:
            q += 1
        return _dec(self._sign, q, exp)

    def _round(self, places: int, rounding: str) -> "Decimal":
        # round a nonzero value to places significant digits
        if self._kind != _FINITE or self._int == 0:
            return self
        ans = self._rescale(self.adjusted() + 1 - places, rounding)
        if ans.adjusted() != self.adjusted():
            ans = ans._rescale(ans.adjusted() + 1 - places, rounding)
        return ans

    # ---- arithmetic

    def _unary(self, context: Context, negate: int) -> "Decimal":
        # +self or -self, rounded: a zero's sign follows the rounding mode
        if self._kind != _FINITE:
            nan = self._check_nans(None, context)
            if nan is not None:
                return nan
            return self.copy_negate() if negate else self
        if self._int == 0 and context._rounding != ROUND_FLOOR:
            return _dec(0, 0, self._exp)._fix(context)
        if self._int == 0 and not negate:
            return self._fix(context)
        return (self.copy_negate() if negate else self)._fix(context)

    def __neg__(self) -> "Decimal":
        if self._kind == _FINITE and self._int == 0 and getcontext()._rounding == ROUND_FLOOR:
            return _dec(1, 0, self._exp)._fix(getcontext()) if not self._sign else _dec(0, 0, self._exp)._fix(getcontext())
        return self._unary(getcontext(), 1)

    def __pos__(self) -> "Decimal":
        return self._unary(getcontext(), 0)

    def __abs__(self) -> "Decimal":
        if self._kind != _FINITE:
            nan = self._check_nans(None, getcontext())
            return nan if nan is not None else self.copy_abs()
        return self.copy_abs()._fix(getcontext())

    def _add(self, other: "Decimal", context: Context) -> "Decimal":
        if self._kind != _FINITE or other._kind != _FINITE:
            nan = self._check_nans(other, context)
            if nan is not None:
                return nan
            if self._kind == _INFINITY:
                if other._kind == _INFINITY and self._sign != other._sign:
                    raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
                return self
            return other
        exp = min(self._exp, other._exp)
        negativezero = 1 if context._rounding == ROUND_FLOOR and self._sign != other._sign else 0
        if self._int == 0 and other._int == 0:
            return _dec(1 if negativezero else min(self._sign, other._sign), 0, exp)._fix(context)
        if self._int == 0:
            return other._rescale(max(exp, other._exp - context._prec - 1), context._rounding)._fix(context)
        if other._int == 0:
            return self._rescale(max(exp, self._exp - context._prec - 1), context._rounding)._fix(context)
        # Align the exponents: the operand with the smaller one, if it cannot affect the rounded
        # result's digits, counts as one unit of an exponent just below them.
        a, ae = self._int, self._exp
        b, be = other._int, other._exp
        if ae < be:
            hi, hie, lo, loe = b, be, a, ae
        else:
            hi, hie, lo, loe = a, ae, b, be
        low = hie + min(-1, _ndigits(hi) - context._prec - 2)
        if _ndigits(lo) + loe - 1 < low:
            lo = 1
            loe = low
        hi *= 10 ** (hie - loe)
        if ae < be:
            a, b = lo, hi
        else:
            a, b = hi, lo
        total = (-a if self._sign else a) + (-b if other._sign else b)
        if total == 0:
            return _dec(negativezero, 0, exp)._fix(context)
        return _dec(1 if total < 0 else 0, abs(total), loe)._fix(context)

    def _mul(self, other: "Decimal", context: Context) -> "Decimal":
        sign = self._sign ^ other._sign
        if self._kind != _FINITE or other._kind != _FINITE:
            nan = self._check_nans(other, context)
            if nan is not None:
                return nan
            if (self._kind == _INFINITY and other._int == 0 and other._kind == _FINITE) or (other._kind == _INFINITY and self._int == 0 and self._kind == _FINITE):
                raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
            return _dec(sign, 0, 0, _INFINITY)
        return _dec(sign, self._int * other._int, self._exp + other._exp)._fix(context)

    def _div(self, other: "Decimal", context: Context) -> "Decimal":
        sign = self._sign ^ other._sign
        if self._kind != _FINITE or other._kind != _FINITE:
            nan = self._check_nans(other, context)
            if nan is not None:
                return nan
            if self._kind == _INFINITY and other._kind == _INFINITY:
                raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
            if self._kind == _INFINITY:
                return _dec(sign, 0, 0, _INFINITY)
            return _dec(sign, 0, context.Etiny())
        if other._int == 0:
            if self._int == 0:
                raise InvalidOperation("[<class 'decimal.DivisionUndefined'>]")
            raise DivisionByZero("[<class 'decimal.DivisionByZero'>]")
        if self._int == 0:
            return _dec(sign, 0, self._exp - other._exp)._fix(context)
        shift = _ndigits(other._int) - _ndigits(self._int) + context._prec + 1
        exp = self._exp - other._exp - shift
        if shift >= 0:
            coeff, remainder = divmod(self._int * 10 ** shift, other._int)
        else:
            coeff, remainder = divmod(self._int, other._int * 10 ** -shift)
        if remainder != 0:
            if coeff % 5 == 0:
                coeff += 1  # (so that the digits cut off are neither zeros nor an exact half)
        else:
            ideal = self._exp - other._exp
            while exp < ideal and coeff % 10 == 0:
                coeff //= 10
                exp += 1
        return _dec(sign, coeff, exp)._fix(context)

    def _divide(self, other: "Decimal", context: Context) -> "tuple[Decimal, Decimal]":
        # the integer quotient and the remainder of two finite values (other nonzero or infinite)
        sign = self._sign ^ other._sign
        ideal = self._exp if other._kind == _INFINITY else min(self._exp, other._exp)
        expdiff = self.adjusted() - other.adjusted()
        if self._int == 0 or other._kind == _INFINITY or expdiff <= -2:
            return _dec(sign, 0, 0), self._rescale(ideal, context._rounding)
        if expdiff <= context._prec:
            a, b = self._int, other._int
            if self._exp >= other._exp:
                a *= 10 ** (self._exp - other._exp)
            else:
                b *= 10 ** (other._exp - self._exp)
            q, r = divmod(a, b)
            if q < 10 ** context._prec:
                return _dec(sign, q, 0), _dec(self._sign, r, ideal)
        raise InvalidOperation("[<class 'decimal.DivisionImpossible'>]")

    def _divmod(self, other: "Decimal", context: Context) -> "tuple[Decimal, Decimal]":
        nan = self._check_nans(other, context)
        if nan is not None:
            return nan, nan
        if self._kind == _INFINITY:
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        if other._kind == _FINITE and other._int == 0:
            if self._int == 0:
                raise InvalidOperation("[<class 'decimal.DivisionUndefined'>]")
            # (both of CPython's signals for x // 0 and x % 0: the first trapped one is raised)
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>, <class 'decimal.DivisionByZero'>]")
        quotient, remainder = self._divide(other, context)
        if other._kind == _INFINITY:
            return quotient, remainder._fix(context)  # (the zero quotient of an infinite divisor is as it is)
        return quotient._fix(context), remainder._fix(context)

    def _mod(self, other: "Decimal", context: Context) -> "Decimal":
        nan = self._check_nans(other, context)
        if nan is not None:
            return nan
        if self._kind == _INFINITY:
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        if other._kind == _FINITE and other._int == 0:
            if self._int == 0:
                raise InvalidOperation("[<class 'decimal.DivisionUndefined'>]")
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        return self._divide(other, context)[1]._fix(context)

    def _floordiv(self, other: "Decimal", context: Context) -> "Decimal":
        nan = self._check_nans(other, context)
        if nan is not None:
            return nan
        if self._kind == _INFINITY:
            if other._kind == _INFINITY:
                raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
            return _dec(self._sign ^ other._sign, 0, 0, _INFINITY)
        if other._kind == _FINITE and other._int == 0:
            if self._int == 0:
                raise InvalidOperation("[<class 'decimal.DivisionUndefined'>]")
            raise DivisionByZero("[<class 'decimal.DivisionByZero'>]")
        # (the context's exponent limits apply to an integer quotient too: Overflow past Emax,
        # and zeros appended for a clamped exponent; the zero of an infinite divisor is as it is)
        quotient = self._divide(other, context)[0]
        return quotient if other._kind == _INFINITY else quotient._fix(context)

    def _isinteger(self) -> bool:
        if self._kind != _FINITE:
            return False
        if self._exp >= 0 or self._int == 0:
            return True
        if -self._exp >= _ndigits(self._int):
            return False  # (a fraction below one: no power of ten of its exponent is made)
        return self._int % 10 ** -self._exp == 0

    def _pow(self, other: int, context: Context) -> "Decimal":
        # self ** other for an integer exponent, as CPython's decimal computes it: square and
        # multiply, rounded half-even to a few digits more than the precision, then rounded once
        # to the context
        nan = self._check_nans(None, context)
        if nan is not None:
            return nan
        sign = 1 if self._sign == 1 and other % 2 == 1 else 0
        if self._kind == _FINITE and self._int == 0:
            if other == 0:
                raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
            return _dec(sign, 0, 0) if other > 0 else _dec(sign, 0, 0, _INFINITY)
        if other == 0:
            return _dec(0, 1, 0)
        if self._kind == _INFINITY:
            return _dec(sign, 0, 0, _INFINITY) if other > 0 else _dec(sign, 0, 0)
        prec = context._prec
        base = self.copy_abs()
        if base._cmp(_dec(0, 1, 0)) == 0:
            # 1 ** n (and -1 ** n, but for its sign) is 1 with the exponent of the exact product, as far as the precision allows
            shift = min(-self._exp * other, prec - 1) if other > 0 else 0
            return _dec(sign, 10 ** shift, -shift)
        # A result certainly beyond the exponent limits is not computed: _fix() raises Overflow
        # for the one and rounds the other to zero or the smallest subnormal.
        adj = base.adjusted()
        if adj > 0:
            zeta = _ndigits(adj) - 1
        elif adj < -1:
            zeta = _ndigits(-adj - 1) - 1
        else:
            exp = min(base._exp, 0)
            distance = abs(base._int * 10 ** (base._exp - exp) - 10 ** -exp)  # abs(base - 1) * 10**-exp
            zeta = (_ndigits(distance) + exp - 1) - (2 if adj == 0 else 1)
        bound = zeta + _ndigits(abs(other)) - 1
        if (adj < 0) == (other < 0):
            if _ndigits(context._emax) < bound:
                return _dec(sign, 1, context._emax + 1)._fix(context)
        elif _ndigits(-context.Etiny()) < bound:
            return _dec(sign, 1, context.Etiny() - 1)._fix(context)
        work = Context(prec + _ndigits(abs(other)) + 2 + (1 if other < 0 else 0), ROUND_HALF_EVEN, context._emin, context._emax, 1, 0)
        if other < 0:
            base = _dec(0, 1, 0)._div(base, work)
        result = base
        n = abs(other)
        bit = 1 << (n.bit_length() - 1)
        bit >>= 1
        while bit != 0:
            result = result._mul(result, work)
            if n & bit:
                result = result._mul(base, work)
            if result._int == 0:
                break
            bit >>= 1
        return _dec(sign, result._int, result._exp)._fix(context)

    def __pow__(self, other: int) -> "Decimal":
        return self._pow(other, getcontext())

    def sqrt(self, context: Context | None = None) -> "Decimal":
        """The square root, correctly rounded half-even to the context's precision."""
        ctx = getcontext() if context is None else context
        if self._kind != _FINITE:
            nan = self._check_nans(None, ctx)
            if nan is not None:
                return nan
            if self._sign == 0:
                return self
        if self._kind == _FINITE and self._int == 0:
            return _dec(self._sign, 0, self._exp // 2)._fix(ctx)
        if self._sign == 1:
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        prec = ctx._prec + 1
        # self = c * 100**e with c an integer of about 2 * prec digits: its integer square root
        # has prec digits, one more than the context's precision
        digits = _ndigits(self._int)
        e = self._exp >> 1
        if self._exp & 1:
            c = self._int * 10
            l = (digits >> 1) + 1
        else:
            c = self._int
            l = (digits + 1) >> 1
        shift = prec - l
        exact = True
        if shift >= 0:
            c *= 100 ** shift
        else:
            c, remainder = divmod(c, 100 ** -shift)
            exact = remainder == 0
        e -= shift
        n = 10 ** prec
        while True:
            q = c // n
            if n <= q:
                break
            n = (n + q) >> 1
        exact = exact and n * n == c
        if exact:
            if shift >= 0:
                n //= 10 ** shift
            else:
                n *= 10 ** -shift
            e += shift
        elif n % 5 == 0:
            n += 1  # (inexact: the digits cut off are neither zeros nor an exact half)
        half_even = ctx.copy()
        half_even._rounding = ROUND_HALF_EVEN
        return _dec(0, n, e)._fix(half_even)

    def fma(self, other: "Decimal", third: "Decimal", context: Context | None = None) -> "Decimal":
        """self * other + third, with no rounding of the product."""
        ctx = getcontext() if context is None else context
        if self._kind != _FINITE or other._kind != _FINITE:
            if self._kind == _SNAN or other._kind == _SNAN or third._kind == _SNAN:
                raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
            if self._kind == _NAN:
                return self._fix_nan(ctx)
            if other._kind == _NAN:
                return other._fix_nan(ctx)
            if (self._kind == _INFINITY and other._int == 0 and other._kind == _FINITE) or (other._kind == _INFINITY and self._int == 0 and self._kind == _FINITE):
                raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
            product = _dec(self._sign ^ other._sign, 0, 0, _INFINITY)
        else:
            product = _dec(self._sign ^ other._sign, self._int * other._int, self._exp + other._exp)
        return product._add(third, ctx)

    def __add__(self, other):
        return self._add(_operand(other, "+"), getcontext())

    def __radd__(self, other: int) -> "Decimal":
        return _from_int(other)._add(self, getcontext())

    def __sub__(self, other):
        o = _operand(other, "-")
        return self._add(o.copy_negate() if o._kind < _NAN else o, getcontext())

    def __rsub__(self, other: int) -> "Decimal":
        return _from_int(other)._add(self.copy_negate() if self._kind < _NAN else self, getcontext())

    def __mul__(self, other):
        return self._mul(_operand(other, "*"), getcontext())

    def __rmul__(self, other: int) -> "Decimal":
        return _from_int(other)._mul(self, getcontext())

    def __truediv__(self, other):
        return self._div(_operand(other, "/"), getcontext())

    def __rtruediv__(self, other: int) -> "Decimal":
        return _from_int(other)._div(self, getcontext())

    def __floordiv__(self, other):
        return self._floordiv(_operand(other, "//"), getcontext())

    def __rfloordiv__(self, other: int) -> "Decimal":
        return _from_int(other)._floordiv(self, getcontext())

    def __mod__(self, other):
        return self._mod(_operand(other, "%"), getcontext())

    def __rmod__(self, other: int) -> "Decimal":
        return _from_int(other)._mod(self, getcontext())

    def __divmod__(self, other: "Decimal") -> "tuple[Decimal, Decimal]":
        return self._divmod(other, getcontext())

    def remainder_near(self, other: "Decimal", context: Context | None = None) -> "Decimal":
        """self - other * n, for the integer n nearest to self / other (ties to even)."""
        ctx = getcontext() if context is None else context
        nan = self._check_nans(other, ctx)
        if nan is not None:
            return nan
        if self._kind == _INFINITY:
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        if other._kind == _FINITE and other._int == 0:
            raise InvalidOperation("[<class 'decimal.DivisionUndefined'>]" if self._int == 0 else "[<class 'decimal.InvalidOperation'>]")
        if other._kind == _INFINITY:
            return self._fix(ctx)
        ideal = min(self._exp, other._exp)
        if self._int == 0:
            return _dec(self._sign, 0, ideal)._fix(ctx)
        expdiff = self.adjusted() - other.adjusted()
        if expdiff >= ctx._prec + 1:
            raise InvalidOperation("[<class 'decimal.DivisionImpossible'>]")
        if expdiff <= -2:
            return self._rescale(ideal, ctx._rounding)._fix(ctx)
        a, b = self._int, other._int
        if self._exp >= other._exp:
            a *= 10 ** (self._exp - other._exp)
        else:
            b *= 10 ** (other._exp - self._exp)
        q, r = divmod(a, b)
        if 2 * r + (q & 1) > b:
            r -= b
            q += 1
        if q >= 10 ** ctx._prec:
            raise InvalidOperation("[<class 'decimal.DivisionImpossible'>]")
        sign = self._sign
        if r < 0:
            sign = 1 - sign
            r = -r
        return _dec(sign, r, ideal)._fix(ctx)

    # ---- comparison

    def _cmp(self, other: "Decimal") -> int:
        # -1, 0 or 1 as self is less than, equal to or greater than other (neither a NaN)
        if self._kind != _FINITE or other._kind != _FINITE:
            a = (-1 if self._sign else 1) if self._kind == _INFINITY else 0
            b = (-1 if other._sign else 1) if other._kind == _INFINITY else 0
            return 0 if a == b else -1 if a < b else 1
        if self._int == 0:
            if other._int == 0:
                return 0
            return 1 if other._sign else -1
        if other._int == 0:
            return -1 if self._sign else 1
        if other._sign < self._sign:
            return -1
        if self._sign < other._sign:
            return 1
        greater = -1 if self._sign else 1
        self_adjusted = self.adjusted()
        other_adjusted = other.adjusted()
        if self_adjusted == other_adjusted:
            a = self._int * 10 ** max(self._exp - other._exp, 0)
            b = other._int * 10 ** max(other._exp - self._exp, 0)
            return 0 if a == b else -greater if a < b else greater
        return greater if self_adjusted > other_adjusted else -greater

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Decimal):
            if self._kind >= _NAN or other._kind >= _NAN:
                if self._kind == _SNAN or other._kind == _SNAN:
                    raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
                return False
            return self._cmp(other) == 0
        if isinstance(other, bool):
            return self == _from_int(1 if other else 0)
        if isinstance(other, int):
            return self == _from_int(other)
        if isinstance(other, float):
            return self == Decimal(other)
        return False

    def _order(self, other: "Decimal") -> int:
        if self._kind >= _NAN or other._kind >= _NAN:
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        return self._cmp(other)

    def __lt__(self, other) -> bool:
        return self._order(_comparand(other)) < 0

    def __le__(self, other) -> bool:
        return self._order(_comparand(other)) <= 0

    def __gt__(self, other) -> bool:
        return self._order(_comparand(other)) > 0

    def __ge__(self, other) -> bool:
        return self._order(_comparand(other)) >= 0

    def compare(self, other: "Decimal", context: Context | None = None) -> "Decimal":
        """Decimal -1, 0 or 1 as self is less than, equal to or greater than other; NaN for a NaN."""
        if self._kind != _FINITE or other._kind != _FINITE:
            nan = self._check_nans(other, getcontext() if context is None else context)
            if nan is not None:
                return nan
        c = self._cmp(other)
        return _dec(1 if c < 0 else 0, abs(c), 0)

    def max(self, other: "Decimal", context: Context | None = None) -> "Decimal":
        """The larger value, rounded to the context: a number rather than a quiet NaN."""
        ctx = getcontext() if context is None else context
        return self._extreme(other, ctx, 1)

    def min(self, other: "Decimal", context: Context | None = None) -> "Decimal":
        """The smaller value, rounded to the context: a number rather than a quiet NaN."""
        ctx = getcontext() if context is None else context
        return self._extreme(other, ctx, -1)

    def _extreme(self, other: "Decimal", ctx: Context, want: int) -> "Decimal":
        if self._kind != _FINITE or other._kind != _FINITE:
            if self._kind == _NAN and other._kind < _NAN:
                return other._fix(ctx)
            if other._kind == _NAN and self._kind < _NAN:
                return self._fix(ctx)
            nan = self._check_nans(other, ctx)
            if nan is not None:
                return nan
        c = self._cmp(other)
        if c == 0:
            c = self._compare_total(other)
        ans = self if c == want else other
        return ans._fix(ctx)

    def _compare_total(self, other: "Decimal") -> int:
        # the total order of two numerically equal numbers: by sign, then by exponent
        if self._sign != other._sign:
            return -1 if self._sign else 1
        if self._exp == other._exp:
            return 0
        low = -1 if self._exp < other._exp else 1
        return -low if self._sign else low

    def __hash__(self) -> int:
        if self._kind != _FINITE:
            if self._kind == _SNAN:
                raise TypeError("Cannot hash a signaling NaN value")
            if self._kind == _NAN:
                return 0  # (CPython hashes a NaN by its identity: any value serves, as a NaN equals nothing)
            return -_HASH_INF if self._sign else _HASH_INF
        if self._exp >= 0:
            exp_hash = pow(10, self._exp, _HASH_MODULUS)
        else:
            exp_hash = pow(_HASH_10INV, -self._exp, _HASH_MODULUS)
        ans = self._int * exp_hash % _HASH_MODULUS
        if self._sign and self._int != 0:
            ans = -ans
        return -2 if ans == -1 else ans

    # ---- conversion

    def __bool__(self) -> bool:
        return self._kind != _FINITE or self._int != 0

    def __int__(self) -> int:
        if self._kind != _FINITE:
            if self._kind >= _NAN:
                raise ValueError("cannot convert NaN to integer")
            raise OverflowError("cannot convert Infinity to integer")
        if self._int == 0 or (self._exp < 0 and -self._exp >= _ndigits(self._int)):
            return 0  # (zero, or a fraction below one: no power of ten of its exponent is made)
        n = self._int * 10 ** self._exp if self._exp >= 0 else self._int // 10 ** -self._exp
        return -n if self._sign else n

    def __trunc__(self) -> int:
        return self.__int__()

    def __floor__(self) -> int:
        n = self.__int__()
        return n - 1 if self._sign and not self._isinteger() else n

    def __ceil__(self) -> int:
        n = self.__int__()
        return n + 1 if not self._sign and not self._isinteger() else n

    def __float__(self) -> float:
        if self._kind >= _NAN:
            if self._kind == _SNAN:
                raise ValueError("cannot convert signaling NaN to float")
            return float("-nan") if self._sign else float("nan")
        return float(self._text(False, getcontext()))

    def __round__(self, n=None):
        # round(d) is the nearest int (ties to even); round(d, n) is a Decimal with n fraction digits
        if n is None:
            if self._kind != _FINITE:
                if self._kind >= _NAN:
                    raise ValueError("cannot convert NaN to integer")
                raise OverflowError("cannot convert Infinity to integer")
            return self._rescale(0, ROUND_HALF_EVEN).__int__()
        return self.quantize(_dec(0, 1, -n))

    def quantize(self, exp: "Decimal", rounding: str | None = None, context: Context | None = None) -> "Decimal":
        """The value rounded to the exponent of exp: Decimal('1.41421').quantize(Decimal('0.01'))."""
        ctx = getcontext() if context is None else context
        mode = ctx._rounding if rounding is None else rounding
        if mode not in _ROUNDINGS:
            raise TypeError("valid values for rounding are:\n  [ROUND_CEILING, ROUND_FLOOR, ROUND_UP, ROUND_DOWN,\n   ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN,\n   ROUND_05UP]")
        if self._kind != _FINITE or exp._kind != _FINITE:
            nan = self._check_nans(exp, ctx)
            if nan is not None:
                return nan
            if exp._kind == _INFINITY and self._kind == _INFINITY:
                return self
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        if not (ctx.Etiny() <= exp._exp <= ctx._emax):
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        if self._int == 0:
            return _dec(self._sign, 0, exp._exp)._fix(ctx)
        self_adjusted = self.adjusted()
        if self_adjusted > ctx._emax or self_adjusted - exp._exp + 1 > ctx._prec:
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        ans = self._rescale(exp._exp, mode)
        if ans.adjusted() > ctx._emax or _ndigits(ans._int) > ctx._prec:
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        return ans._fix(ctx)

    def to_integral_value(self, rounding: str | None = None, context: Context | None = None) -> "Decimal":
        """The value rounded to an integer, as a Decimal."""
        ctx = getcontext() if context is None else context
        if self._kind != _FINITE:
            nan = self._check_nans(None, ctx)
            return nan if nan is not None else self
        if self._exp >= 0:
            return self
        return self._rescale(0, ctx._rounding if rounding is None else rounding)

    def to_integral_exact(self, rounding: str | None = None, context: Context | None = None) -> "Decimal":
        return self.to_integral_value(rounding, context)

    def to_integral(self, rounding: str | None = None, context: Context | None = None) -> "Decimal":
        return self.to_integral_value(rounding, context)

    def normalize(self, context: Context | None = None) -> "Decimal":
        """The value with trailing zeros of its coefficient removed: Decimal('32.100') to Decimal('32.1')."""
        ctx = getcontext() if context is None else context
        if self._kind != _FINITE:
            nan = self._check_nans(None, ctx)
            if nan is not None:
                return nan
        dup = self._fix(ctx)
        if dup._kind == _INFINITY:
            return dup
        if dup._int == 0:
            return _dec(dup._sign, 0, 0)
        exp_max = ctx.Etop() if ctx._clamp else ctx._emax
        coeff = dup._int
        exp = dup._exp
        while coeff % 10 == 0 and exp < exp_max:
            coeff //= 10
            exp += 1
        return _dec(dup._sign, coeff, exp)

    def scaleb(self, other: int, context: Context | None = None) -> "Decimal":
        """The value with other added to its exponent."""
        ctx = getcontext() if context is None else context
        if self._kind != _FINITE:
            nan = self._check_nans(None, ctx)
            return nan if nan is not None else self
        limit = 2 * (ctx._emax + ctx._prec)
        if other < -limit or other > limit:
            raise InvalidOperation("[<class 'decimal.InvalidOperation'>]")
        return _dec(self._sign, self._int, self._exp + other)._fix(ctx)

    # ---- text

    def _text(self, eng: bool, context: Context) -> str:
        sign = "-" if self._sign else ""
        if self._kind != _FINITE:
            if self._kind == _INFINITY:
                return sign + "Infinity"
            return sign + ("NaN" if self._kind == _NAN else "sNaN") + (str(self._int) if self._int != 0 else "")
        digits = str(self._int)
        leftdigits = self._exp + len(digits)
        if self._exp <= 0 and leftdigits > -6:
            dotplace = leftdigits  # no exponent needed
        elif not eng:
            dotplace = 1  # scientific notation
        elif self._int == 0:
            dotplace = (leftdigits + 1) % 3 - 1  # engineering notation of a zero
        else:
            dotplace = (leftdigits - 1) % 3 + 1  # engineering notation
        if dotplace <= 0:
            intpart = "0"
            fracpart = "." + "0" * -dotplace + digits
        elif dotplace >= len(digits):
            intpart = digits + "0" * (dotplace - len(digits))
            fracpart = ""
        else:
            intpart = digits[:dotplace]
            fracpart = "." + digits[dotplace:]
        if leftdigits == dotplace:
            return sign + intpart + fracpart
        return sign + intpart + fracpart + ("E" if context._capitals else "e") + _signed_text(leftdigits - dotplace)

    def __str__(self) -> str:
        return self._text(False, getcontext())

    def __repr__(self) -> str:
        return "Decimal('" + self._text(False, getcontext()) + "')"

    def to_eng_string(self, context: Context | None = None) -> str:
        """The value in engineering notation: an exponent, if any, that is a multiple of 3."""
        return self._text(True, getcontext() if context is None else context)

    def __format__(self, specifier: str) -> str:
        spec = _FormatSpec(specifier)
        context = getcontext()
        if self._kind != _FINITE:
            body = self.copy_abs()._text(False, context)
            return spec.align(spec.sign_text(self._sign == 1), body + "%" if spec.kind == "%" else body)
        kind = spec.kind
        if kind == "":
            kind = "G" if context._capitals else "g"
        value = self
        if kind == "%":
            value = _dec(self._sign, self._int, self._exp + 2)
        rounding = context._rounding
        precision = spec.precision
        if precision >= 0:
            if kind == "e" or kind == "E":
                value = value._round(precision + 1, rounding)
            elif kind == "f" or kind == "F" or kind == "%":
                value = value._rescale(-precision, rounding)
            elif _ndigits(value._int) > precision:
                value = value._round(precision, rounding)
        if value._int == 0 and value._exp > 0 and (kind == "f" or kind == "F" or kind == "%"):
            value = value._rescale(0, rounding)
        negative = value._sign == 1 and not (value._int == 0 and spec.no_neg_0)
        digits = str(value._int)
        leftdigits = value._exp + len(digits)
        if kind == "e" or kind == "E":
            dotplace = 1 - precision if value._int == 0 and precision >= 0 else 1
        elif kind == "f" or kind == "F" or kind == "%":
            dotplace = leftdigits
        elif value._exp <= 0 and leftdigits > -6:
            dotplace = leftdigits
        else:
            dotplace = 1
        if dotplace < 0:
            intpart = "0"
            fracpart = "0" * -dotplace + digits
        elif dotplace > len(digits):
            intpart = digits + "0" * (dotplace - len(digits))
            fracpart = ""
        else:
            intpart = digits[:dotplace] if dotplace > 0 else "0"
            fracpart = digits[dotplace:]
        exp = leftdigits - dotplace
        sign = spec.sign_text(negative)
        if fracpart != "" or spec.alt:
            fracpart = "." + fracpart
        if exp != 0 or kind == "e" or kind == "E":
            fracpart += ("E" if kind == "E" or kind == "G" else "e") + _signed_text(exp)
        if kind == "%":
            fracpart += "%"
        min_width = spec.width - len(fracpart) - len(sign) if spec.zeropad else 0
        return spec.align(sign, _group(intpart, spec.separator, min_width) + fracpart)


class _FormatSpec:
    # [[fill]align][sign][z][#][0][width][, or _][.precision][type], as CPython's decimal reads it

    def __init__(self, text: str) -> None:
        self.fill = " "
        self.alignment = ">"
        self.sign = "-"
        self.no_neg_0 = False
        self.alt = False
        self.zeropad = False
        self.width = 0
        self.separator = ""
        self.precision = -1
        self.kind = ""
        n = len(text)
        i = 0
        explicit = False
        if n >= 2 and text[1] in "<>=^":
            self.fill = text[0]
            self.alignment = text[1]
            explicit = True
            i = 2
        elif n >= 1 and text[0] in "<>=^":
            self.alignment = text[0]
            i = 1
        aligned = i > 0
        if i < n and text[i] in "-+ ":
            self.sign = text[i]
            i += 1
        if i < n and text[i] == "z":
            self.no_neg_0 = True
            i += 1
        if i < n and text[i] == "#":
            self.alt = True
            i += 1
        if i < n and text[i] == "0":
            self.zeropad = True
            i += 1
        start = i
        while i < n and text[i].isdecimal() and not (i == start and text[i] == "0"):
            i += 1
        if i > start:
            self.width = int(text[start:i])
        if i < n and (text[i] == "," or text[i] == "_"):
            self.separator = text[i]
            i += 1
        if i < n and text[i] == ".":
            start = i + 1
            j = start
            while j < n and text[j].isdecimal():
                j += 1
            if j == start:
                raise ValueError("invalid format string")
            self.precision = int(text[start:j])
            i = j
        if i < n and text[i] in "eEfFgGn%":
            self.kind = text[i]
            i += 1
        if i != n:
            raise ValueError("invalid format string")
        if self.zeropad and explicit:
            raise ValueError("invalid format string")
        if self.zeropad and aligned:
            raise ValueError("invalid format string")
        if self.precision == 0 and self.kind in ("", "g", "G", "n"):
            self.precision = 1
        if self.kind == "n":
            # (the C locale's number format: no grouping, a "." decimal point)
            if self.separator != "":
                raise ValueError("invalid format string")
            self.kind = "g"

    def sign_text(self, negative: bool) -> str:
        if negative:
            return "-"
        return self.sign if self.sign != "-" else ""

    def align(self, sign: str, body: str) -> str:
        padding = self.fill * (self.width - len(sign) - len(body))
        if self.alignment == "<":
            return sign + body + padding
        if self.alignment == ">":
            return padding + sign + body
        if self.alignment == "=":
            return sign + padding + body
        half = len(padding) // 2
        return padding[:half] + sign + body + padding[half:]


def _group(digits: str, sep: str, min_width: int) -> str:
    # the integer digits in groups of three joined by sep, zero-padded to min_width characters
    if sep == "":
        return digits.rjust(max(min_width, 1), "0")
    groups: list[str] = []
    while True:
        l = min(max(len(digits), min_width, 1), 3)
        groups.append("0" * (l - len(digits)) + digits[len(digits) - l:] if len(digits) >= l else "0" * (l - len(digits)) + digits)
        digits = digits[: len(digits) - l] if len(digits) > l else ""
        min_width -= l
        if digits == "" and min_width <= 0:
            break
        min_width -= len(sep)
    groups.reverse()
    return sep.join(groups)


def _dec(sign: int, coeff: int, exp: int, kind: int = 0) -> Decimal:
    d = Decimal(0)
    d._sign = sign
    d._int = coeff
    d._exp = exp
    d._kind = kind
    return d


def _from_int(value: int) -> Decimal:
    return _dec(1 if value < 0 else 0, abs(value), 0)


def _operand(other, op: str) -> Decimal:
    # the other operand of an arithmetic operator: a Decimal or an int (CPython's TypeError otherwise)
    if isinstance(other, Decimal):
        return other
    if isinstance(other, bool):
        return _from_int(1 if other else 0)
    if isinstance(other, int):
        return _from_int(other)
    raise TypeError(f"unsupported operand type(s) for {op}: 'decimal.Decimal' and '{type(other).__name__}'")


def _comparand(other) -> Decimal:
    # the other operand of an ordering comparison: a Decimal, an int or a float (its exact value)
    if isinstance(other, Decimal):
        return other
    if isinstance(other, bool):
        return _from_int(1 if other else 0)
    if isinstance(other, int):
        return _from_int(other)
    if isinstance(other, float):
        return Decimal(other)
    raise TypeError(f"'<' not supported between instances of 'decimal.Decimal' and '{type(other).__name__}'")


DefaultContext = Context(prec=28, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999, capitals=1, clamp=0)
_template = DefaultContext
BasicContext = Context(prec=9, rounding=ROUND_HALF_UP)
ExtendedContext = Context(prec=9, rounding=ROUND_HALF_EVEN)
