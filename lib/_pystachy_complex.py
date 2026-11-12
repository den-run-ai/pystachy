"""The complex type of the builtins, as a class of the subset.

Pystachy's own module, after CPython 3.13's Objects/complexobject.c: a complex literal (1j) and
complex() make an object of this class, whose two floats no code changes. Its arithmetic is that
file's, operation for operation, so that each result has CPython's last bit: a real operand is
first made the complex number of it (x + 0.0j), as CPython 3.13 does, and the quotient is Smith's.
abs() and ** read libm's errno there, so they are runtime.c's (the __pys_cx_* calls are compiler
primitives: _Py_c_abs, and complex_pow with c_powi and _Py_c_pow). The compiler loads this module
for a program that may use a complex number (analysis.complex_values, Loader.program); programs
do not import it, and it runs no code. An operator's other operand is typed where it is called,
as any template's is. A real number on the left calls the reflected method: where its type is
known, the compiler calls the method's own (_radd of __radd__) with the float of it (Gen.dunder).
"""


class complex:
    __slots__ = ("real", "imag")

    def __init__(self, real: float, imag: float) -> None:
        self.real = real
        self.imag = imag

    def conjugate(self) -> "complex":
        return complex(self.real, -self.imag)

    def __repr__(self) -> str:
        # complex_repr: the real part is left out where it is +0.0, with the parentheses
        if self.real == 0.0 and not _negative(self.real):
            return _part(self.imag) + "j"
        return "(" + _part(self.real) + ("" if _negative(self.imag) else "+") + _part(self.imag) + "j)"

    def __hash__(self) -> int:
        # complex_hash: hash(real) + 1000003 * hash(imag), in 64 bits that wrap
        a = hash(self.real)
        b = hash(self.imag)
        low = (a & 4294967295) + ((1000003 * (b & 4294967295)) & 4294967295)
        high = ((a >> 32) + ((1000003 * (b & 4294967295)) >> 32) + 1000003 * (b >> 32) + (low >> 32)) & 4294967295
        h = (high - 4294967296 if high >= 2147483648 else high) * 4294967296 + (low & 4294967295)
        return -2 if h == -1 else h

    def __bool__(self) -> bool:
        return self.real != 0.0 or self.imag != 0.0

    def __neg__(self) -> "complex":
        return complex(-self.real, -self.imag)

    def __pos__(self) -> "complex":
        return complex(self.real, self.imag)

    def __abs__(self) -> float:
        return __pys_cx_abs(self.real, self.imag)

    def __eq__(self, other) -> bool:
        if isinstance(other, complex):
            return self.real == other.real and self.imag == other.imag
        if isinstance(other, (int, float)):
            return self.imag == 0.0 and self.real == other  # (an int as CPython compares it with a float: exactly)
        return False

    def __ne__(self, other) -> bool:
        if isinstance(other, complex):
            return self.real != other.real or self.imag != other.imag
        if isinstance(other, (int, float)):
            return self.imag != 0.0 or self.real != other
        return True

    def __add__(self, other):
        if isinstance(other, complex):
            return complex(self.real + other.real, self.imag + other.imag)
        if isinstance(other, (int, float)):
            return complex(self.real + float(other), self.imag + 0.0)
        raise TypeError(_operands("+", "complex", type(other).__name__))

    def __radd__(self, other: bool | int | float) -> "complex":
        return self._radd(float(other))

    def _radd(self, other: float) -> "complex":
        return complex(other + self.real, 0.0 + self.imag)

    def __sub__(self, other):
        if isinstance(other, complex):
            return complex(self.real - other.real, self.imag - other.imag)
        if isinstance(other, (int, float)):
            return complex(self.real - float(other), self.imag - 0.0)
        raise TypeError(_operands("-", "complex", type(other).__name__))

    def __rsub__(self, other: bool | int | float) -> "complex":
        return self._rsub(float(other))

    def _rsub(self, other: float) -> "complex":
        return complex(other - self.real, 0.0 - self.imag)

    def __mul__(self, other):
        if isinstance(other, complex):
            return _prod(self.real, self.imag, other.real, other.imag)
        if isinstance(other, (int, float)):
            return _prod(self.real, self.imag, float(other), 0.0)
        raise TypeError(_operands("*", "complex", type(other).__name__))

    def __rmul__(self, other: bool | int | float) -> "complex":
        return self._rmul(float(other))

    def _rmul(self, other: float) -> "complex":
        return _prod(other, 0.0, self.real, self.imag)

    def __truediv__(self, other):
        if isinstance(other, complex):
            return _quot(self.real, self.imag, other.real, other.imag, "complex division by zero")
        if isinstance(other, (int, float)):
            return _quot(self.real, self.imag, float(other), 0.0, "complex division by zero")
        raise TypeError(_operands("/", "complex", type(other).__name__))

    def __rtruediv__(self, other: bool | int | float) -> "complex":
        return self._rtruediv(float(other))

    def _rtruediv(self, other: float) -> "complex":
        return _quot(other, 0.0, self.real, self.imag, "complex division by zero")

    def __pow__(self, other):
        if isinstance(other, complex):
            return _pow(self.real, self.imag, other.real, other.imag)
        if isinstance(other, (int, float)):
            return _pow(self.real, self.imag, float(other), 0.0)
        raise TypeError(_operands("** or pow()", "complex", type(other).__name__))

    def __rpow__(self, other: bool | int | float) -> "complex":
        return self._rpow(float(other))

    def _rpow(self, other: float) -> "complex":
        return _pow(other, 0.0, self.real, self.imag)


def _operands(op: str, a: str, b: str) -> str:
    return "unsupported operand type(s) for " + op + ": '" + a + "' and '" + b + "'"


def _negative(x: float) -> bool:
    # is x's sign set as repr() shows it: -0.0's is, a NaN's never
    return repr(x).startswith("-")


def _part(x: float) -> str:
    # PyOS_double_to_string(x, 'r', 0, 0): repr(x) without the ".0" that float's repr adds
    s = repr(x)
    return s[:-2] if s.endswith(".0") else s


def _prod(ar: float, ai: float, br: float, bi: float) -> complex:
    # _Py_c_prod
    return complex(ar * br - ai * bi, ar * bi + ai * br)


def _quot(ar: float, ai: float, br: float, bi: float, zero: str) -> complex:
    # _Py_c_quot: Smith's division, by the part of b that is larger in magnitude
    abr = -br if br < 0.0 else br
    abi = -bi if bi < 0.0 else bi
    if abr >= abi:
        if abr == 0.0:
            raise ZeroDivisionError(zero)
        ratio = bi / br
        denom = br + bi * ratio
        return complex((ar + ai * ratio) / denom, (ai - ar * ratio) / denom)
    if abi >= abr:
        ratio = br / bi
        denom = br * ratio + bi
        return complex((ar * ratio + ai) / denom, (ai * ratio - ar) / denom)
    return complex(float("nan"), float("nan"))  # (a part of b is a NaN)


def _pow(ar: float, ai: float, br: float, bi: float) -> complex:
    # complex_pow: runtime.c's, which raises its ZeroDivisionError and OverflowError
    p = __pys_cx_pow(ar, ai, br, bi)
    return complex(p[0], p[1])


def _new(real=0, imag=None):
    # complex(), complex(x) and complex(x, y), also by the names real and imag: complex_new. A
    # complex x alone is x itself, a str is parsed (_parse), and any other pair of numbers a
    # and b, complex ones too, makes a + b*1j
    if imag is None:
        if isinstance(real, complex):
            return real
        if isinstance(real, str):
            return _parse(real)
        if isinstance(real, (int, float)):
            return complex(float(real), 0.0)
        raise TypeError("complex() first argument must be a string or a number, not '" + type(real).__name__ + "'")
    if isinstance(real, str):
        raise TypeError("complex() can't take second arg if first is a string")
    if isinstance(imag, str):
        raise TypeError("complex() second arg can't be a string")
    if isinstance(real, complex):
        if isinstance(imag, complex):
            return complex(real.real - imag.imag, real.imag + imag.real)
        if isinstance(imag, (int, float)):
            return complex(real.real, real.imag + float(imag))
        raise TypeError("complex() second argument must be a number, not '" + type(imag).__name__ + "'")
    if isinstance(real, (int, float)):
        if isinstance(imag, complex):
            return complex(float(real) - imag.imag, imag.real)
        if isinstance(imag, (int, float)):
            return complex(float(real), float(imag))
        raise TypeError("complex() second argument must be a number, not '" + type(imag).__name__ + "'")
    raise TypeError("complex() first argument must be a string or a number, not '" + type(real).__name__ + "'")


def _space(c: str) -> bool:
    return c == " " or c == "\t" or c == "\n" or c == "\r" or c == "\x0b" or c == "\x0c"


def _digit(c: str) -> bool:
    return c >= "0" and c <= "9"


def _number(s: str, i: int) -> int:
    # the end of the longest float that s holds from i, as PyOS_string_to_double reads one (a
    # sign, digits with a point or an exponent, inf, infinity or nan), or i
    n = len(s)
    j = i
    if j < n and (s[j] == "+" or s[j] == "-"):
        j += 1
    low = s[j : j + 8].lower()
    if low.startswith("infinity"):
        return j + 8
    if low.startswith("inf") or low.startswith("nan"):
        return j + 3
    k = j
    while k < n and _digit(s[k]):
        k += 1
    digits = k - j
    if k < n and s[k] == ".":
        k += 1
        while k < n and _digit(s[k]):
            k += 1
        digits = k - j - 1
    if digits == 0:
        return i
    if k < n and (s[k] == "e" or s[k] == "E"):
        e = k + 1
        if e < n and (s[e] == "+" or s[e] == "-"):
            e += 1
        d = e
        while e < n and _digit(s[e]):
            e += 1
        if e > d:
            k = e
    return k


def _ascii(v: str) -> str:
    # _PyUnicode_TransformDecimalAndSpaceToASCII: a decimal digit of another script is its ASCII
    # digit and white space a space; any other character past ASCII ends the text with a "?"
    out = ""
    for c in v:
        if c < "\x80":
            out += c
        elif c.isspace():
            out += " "
        elif c.isdecimal():
            out += str(int(c))
        else:
            return out + "?"
    return out


def _underscores(s: str, v: str) -> str:
    # _Py_string_to_number_with_underscores: s without its underscores, each of which stands
    # between two digits
    if "_" not in s:
        return s
    out = ""
    prev = ""
    for c in s:
        if c == "\x00":
            raise ValueError("could not convert string to complex: " + repr(v))
        if c == "_":
            if not (prev != "" and _digit(prev)):
                raise ValueError("could not convert string to complex: " + repr(v))
        else:
            out += c
            if prev == "_" and not _digit(c):
                raise ValueError("could not convert string to complex: " + repr(v))
        prev = c
    if prev == "_":
        raise ValueError("could not convert string to complex: " + repr(v))
    return out


def _parse(s: str) -> complex:
    # complex_from_string_inner: [(] x [)], yj, x+yj or x-yj, in white space; j alone is 1j
    bad = "complex() arg is a malformed string"
    s = _underscores(_ascii(s), s)
    n = len(s)
    i = 0
    while i < n and _space(s[i]):
        i += 1
    paren = i < n and s[i] == "("
    if paren:
        i += 1
        while i < n and _space(s[i]):
            i += 1
    x = 0.0
    y = 0.0
    end = _number(s, i)
    if end > i:
        z = float(s[i:end])
        i = end
        if i < n and (s[i] == "+" or s[i] == "-"):
            # <float><signed-float>j | <float><sign>j
            x = z
            end = _number(s, i)
            if end > i:
                y = float(s[i:end])
                i = end
            else:
                y = 1.0 if s[i] == "+" else -1.0
                i += 1
            if not (i < n and (s[i] == "j" or s[i] == "J")):
                raise ValueError(bad)
            i += 1
        elif i < n and (s[i] == "j" or s[i] == "J"):
            i += 1
            y = z
        else:
            x = z
    else:
        # not a float: [<sign>] j
        if i < n and (s[i] == "+" or s[i] == "-"):
            y = 1.0 if s[i] == "+" else -1.0
            i += 1
        else:
            y = 1.0
        if not (i < n and (s[i] == "j" or s[i] == "J")):
            raise ValueError(bad)
        i += 1
    while i < n and _space(s[i]):
        i += 1
    if paren:
        if not (i < n and s[i] == ")"):
            raise ValueError(bad)
        i += 1
        while i < n and _space(s[i]):
            i += 1
    if i != n:
        raise ValueError(bad)
    return complex(x, y)
