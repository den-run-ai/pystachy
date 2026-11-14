"""The complex type of the builtins, as a class of the subset.

Pystachy's own module, after CPython 3.13's Objects/complexobject.c: an imaginary literal, a
complex() call and the arithmetic of a complex number make objects of this class. The compiler
loads this module for a program that may use one (Loader.program); programs do not import it, it
runs no code, and its functions are compiled where a program uses them. The compiler passes each
operand of an operation as its two floats, an int or a float x as (float(x), 0.0), as CPython's
TO_COMPLEX converts it, and calls _sum, _diff, _prod, _quot or _pow with the operands in the
order written. The __pys_complex_* calls are compiler primitives: runtime.c's ports of CPython's
_Py_c_quot, complex_pow and _Py_c_abs, with their errors, and complex_hash. (The module runs no
code: it imports nothing.)
"""


class complex:
    __slots__ = ("real", "imag")

    def __init__(self, real: float, imag: float) -> None:
        self.real = real
        self.imag = imag

    def __repr__(self) -> str:
        # complex_repr: no parentheses for a real part of +0.0 (not -0.0, whose repr has its sign),
        # and the imaginary part's sign always (also a NaN's, which has none: "+nan")
        if self.real == 0.0 and not repr(self.real).startswith("-"):
            return _part(self.imag) + "j"
        im = _part(self.imag)
        return "(" + _part(self.real) + (im if im.startswith("-") else "+" + im) + "j)"

    def __hash__(self) -> int:
        return __pys_complex_hash(self.real, self.imag)

    def __eq__(self, other) -> bool:
        # complex_richcompare's == of a dynamic Any value, also with an int (compared with the
        # real part exactly) or a float (the compiler compares typed numbers itself, complex_cmp,
        # and an object of another class by its own __eq__); != inverts it
        if isinstance(other, complex):
            return self.real == other.real and self.imag == other.imag
        if isinstance(other, (int, float)):
            return self.imag == 0.0 and self.real == other
        return False

    # The arithmetic of a dynamic Any value that holds a complex number (the compiler computes a
    # typed operation itself, complex_arith): the other operand converted as TO_COMPLEX converts
    # it, a real number on the left by the reflected method (the dispatcher passes its float).
    # After the dynamic Any port of claude/blissful-hawking-ve4fwg-complex (#1414).
    def __add__(self, other):
        if isinstance(other, complex):
            return _sum(self.real, self.imag, other.real, other.imag)
        if isinstance(other, (int, float)):
            return _sum(self.real, self.imag, float(other), 0.0)
        raise TypeError(_operands("+", type(other).__name__))

    def __radd__(self, other: bool | int | float) -> "complex":
        return _sum(float(other), 0.0, self.real, self.imag)

    def __sub__(self, other):
        if isinstance(other, complex):
            return _diff(self.real, self.imag, other.real, other.imag)
        if isinstance(other, (int, float)):
            return _diff(self.real, self.imag, float(other), 0.0)
        raise TypeError(_operands("-", type(other).__name__))

    def __rsub__(self, other: bool | int | float) -> "complex":
        return _diff(float(other), 0.0, self.real, self.imag)

    def __mul__(self, other):
        if isinstance(other, complex):
            return _prod(self.real, self.imag, other.real, other.imag)
        if isinstance(other, (int, float)):
            return _prod(self.real, self.imag, float(other), 0.0)
        raise TypeError(_operands("*", type(other).__name__))

    def __rmul__(self, other: bool | int | float) -> "complex":
        return _prod(float(other), 0.0, self.real, self.imag)

    def __truediv__(self, other):
        if isinstance(other, complex):
            return _quot(self.real, self.imag, other.real, other.imag)
        if isinstance(other, (int, float)):
            return _quot(self.real, self.imag, float(other), 0.0)
        raise TypeError(_operands("/", type(other).__name__))

    def __rtruediv__(self, other: bool | int | float) -> "complex":
        return _quot(float(other), 0.0, self.real, self.imag)

    def __pow__(self, other):
        if isinstance(other, complex):
            return _pow(self.real, self.imag, other.real, other.imag)
        if isinstance(other, (int, float)):
            return _pow(self.real, self.imag, float(other), 0.0)
        raise TypeError(_operands("** or pow()", type(other).__name__))

    def __rpow__(self, other: bool | int | float) -> "complex":
        return _pow(float(other), 0.0, self.real, self.imag)

    def __bool__(self) -> bool:
        return self.real != 0.0 or self.imag != 0.0

    def __neg__(self) -> "complex":
        return complex(-self.real, -self.imag)

    def __pos__(self) -> "complex":
        return self  # (CPython's complex_pos: the same object)

    def __abs__(self) -> float:
        return __pys_complex_abs(self.real, self.imag)

    def conjugate(self) -> "complex":
        return complex(self.real, -self.imag)

    def __format__(self, spec: str) -> str:
        if spec == "":
            return self.__repr__()  # (str(self))
        return _format(self.real, self.imag, spec)


def _operands(op: str, other: str) -> str:
    return "unsupported operand type(s) for " + op + ": 'complex' and '" + other + "'"


def _part(x: float) -> str:
    # PyOS_double_to_string(x, 'r', 0, 0): repr() without the ".0" of an integral value
    r = repr(x)
    if r.endswith(".0"):
        return r[:-2]
    return r


def _format(re: float, im: float, spec: str) -> str:
    # format(c, spec) of a nonempty spec: parse_internal_render_format_spec (default alignment >),
    # then format_complex_internal: each part as a float of the type and precision ("" is repr's
    # shortest digits, in parentheses unless the real part is +0.0, which is left out), the
    # imaginary part with its sign, and the whole padded to the width
    n = len(spec)
    fill = " "
    align = ">"
    fill_given = False
    pos = 0
    if n >= 2 and spec[1] in "<>=^":
        fill = spec[0]
        align = spec[1]
        fill_given = True
        pos = 2
    elif n >= 1 and spec[0] in "<>=^":
        align = spec[0]
        pos = 1
    align_given = pos > 0
    sign = ""
    if pos < n and spec[pos] in "+- ":
        sign = spec[pos]
        pos += 1
    nozero = pos < n and spec[pos] == "z"
    if nozero:
        pos += 1
    alt = pos < n and spec[pos] == "#"
    if alt:
        pos += 1
    if not fill_given and pos < n and spec[pos] == "0":
        fill = "0"
        if not align_given:
            align = "="
        pos += 1
    start = pos
    while pos < n and spec[pos].isdecimal():
        pos += 1
    width = int(spec[start:pos]) if pos > start else -1
    group = ""
    if pos < n and spec[pos] == ",":
        group = ","
        pos += 1
    if pos < n and spec[pos] == "_":
        if group != "":
            raise ValueError("Cannot specify both ',' and '_'.")
        group = "_"
        pos += 1
    if pos < n and spec[pos] == "," and group == "_":
        raise ValueError("Cannot specify both ',' and '_'.")
    precision = -1
    if pos < n and spec[pos] == ".":
        pos += 1
        start = pos
        while pos < n and spec[pos].isdecimal():
            pos += 1
        if pos == start:
            raise ValueError("Format specifier missing precision")
        precision = int(spec[start:pos])
    if n - pos > 1:
        raise ValueError(f"Invalid format specifier '{spec}' for object of type 'complex'")
    kind = spec[pos] if n - pos == 1 else ""
    if group != "" and kind not in ["d", "e", "f", "g", "E", "G", "%", "F", ""] and not (group == "_" and kind in ["b", "o", "x", "X"]):
        raise ValueError(f"Cannot specify '{group}' with '{kind}'." if 32 < ord(kind) < 128 else f"Cannot specify '{group}' with '\\x{ord(kind):x}'.")
    if kind not in ["", "e", "E", "f", "F", "g", "G", "n"]:
        raise ValueError(f"Unknown format code '{kind}' for object of type 'complex'" if 32 < ord(kind) < 128 else f"Unknown format code '\\x{ord(kind):x}' for object of type 'complex'")
    if fill == "0":
        raise ValueError("Zero padding is not allowed in complex format specifier")
    if align == "=":
        raise ValueError("'=' alignment flag is not allowed in complex format specifier")
    skip = False
    parens = False
    if kind == "":
        skip = re == 0.0 and not repr(re).startswith("-")
        parens = not skip
    if kind == "n":
        kind = "g"
    if precision < 0:
        precision = 0 if kind == "" else 6
    elif kind == "":
        kind = "g"
    rs = _digits(re, kind, precision, alt, nozero, group)
    ims = _digits(im, kind, precision, alt, nozero, group)
    out = ""
    if not skip:
        out = rs if rs.startswith("-") else sign + rs if sign == "+" or sign == " " else rs
    isign = sign if skip else "+"
    out += (ims if ims.startswith("-") else isign + ims if isign == "+" or isign == " " else ims) + "j"
    if parens:
        out = "(" + out + ")"
    pad = width - len(out)
    if pad <= 0:
        return out
    if align == "<":
        return out + fill * pad
    if align == "^":
        return fill * (pad // 2) + out + fill * (pad - pad // 2)
    return fill * pad + out


def _digits(x: float, kind: str, precision: int, alt: bool, nozero: bool, group: str) -> str:
    # PyOS_double_to_string(x, kind, precision, flags), with its sign but no other, and the
    # separators of group between the digits before the point: a float's own formatting, but
    # for kind "" (repr's digits without ".0": 'r'), which the flags change as there
    if kind != "":
        return format(x, ("z" if nozero else "") + ("#" if alt else "") + group + "." + str(precision) + kind)
    r = _part(x)
    if nozero and r == "-0":
        r = "0"
    if alt and r[-1:].isdigit() and "." not in r:
        e = r.find("e")
        r = r + "." if e < 0 else r[:e] + "." + r[e:]
    if group == "":
        return r
    neg = r.startswith("-")
    if neg:
        r = r[1:]
    k = 0
    while k < len(r) and _digit(r[k]):
        k += 1
    head = r[:k]
    grouped = ""
    while len(head) > 3:
        grouped = group + head[-3:] + grouped
        head = head[:-3]
    return ("-" if neg else "") + head + grouped + r[k:]


def _sum(ar: float, ai: float, br: float, bi: float) -> complex:
    return complex(ar + br, ai + bi)


def _diff(ar: float, ai: float, br: float, bi: float) -> complex:
    return complex(ar - br, ai - bi)


def _prod(ar: float, ai: float, br: float, bi: float) -> complex:
    return complex(ar * br - ai * bi, ar * bi + ai * br)


def _quot(ar: float, ai: float, br: float, bi: float) -> complex:
    q = __pys_complex_quot(ar, ai, br, bi)
    return complex(q[0], q[1])


def _pow(ar: float, ai: float, br: float, bi: float) -> complex:
    p = __pys_complex_pow(ar, ai, br, bi)
    return complex(p[0], p[1])


def _two(rr: float, ri: float, rc: bool, ir: float, ii: float, ic: bool) -> complex:
    # complex(r, i) of r = (rr, ri) and i = (ir, ii), each a complex number where rc or ic says
    # so (else its imaginary part is 0.0): r + i * 1j, as complex_new_impl computes it
    re = rr
    im = ir
    if ic:
        re -= ii
    if rc:
        im += ri
    return complex(re, im)


def _from_str(v: str) -> complex:
    # complex(v) of a string: complex_subtype_from_string, which first makes each Unicode digit
    # an ASCII one and each Unicode space a space (the rest ends at a '?'), then drops the
    # underscores between digits (_Py_string_to_number_with_underscores)
    s = v
    if not v.isascii():
        out: list[str] = []
        for ch in v:
            if ord(ch) < 127:
                out.append(ch)
            elif ch.isspace():
                out.append(" ")
            elif ch.isdecimal():
                out.append(str(int(ch)))
            else:
                out.append("?")
                break
        s = "".join(out)
    if "_" in s:
        kept: list[str] = []
        prev = ""
        for ch in s:
            if ch == "\0":
                raise ValueError(f"could not convert string to complex: {v!r}")
            if ch == "_":
                if not _digit(prev):
                    raise ValueError(f"could not convert string to complex: {v!r}")
            else:
                if prev == "_" and not _digit(ch):
                    raise ValueError(f"could not convert string to complex: {v!r}")
                kept.append(ch)
            prev = ch
        if prev == "_":
            raise ValueError(f"could not convert string to complex: {v!r}")
        s = "".join(kept)
    return _parse(s)


def _digit(ch: str) -> bool:
    return len(ch) == 1 and "0" <= ch <= "9"


def _space(ch: str) -> bool:
    return ch == " " or ch == "\t" or ch == "\n" or ch == "\r" or ch == "\x0b" or ch == "\x0c"


def _parse(s: str) -> complex:
    # complex_from_string_inner: <float>, <float>j, <float><signed-float>j, and the forms
    # <float><sign>j, <sign>j and j, in white space and maybe parentheses
    n = len(s)
    i = 0
    x = 0.0
    y = 0.0
    while i < n and _space(s[i]):
        i += 1
    bracket = i < n and s[i] == "("
    if bracket:
        i += 1
        while i < n and _space(s[i]):
            i += 1
    end = _float_end(s, i)
    if end != i:
        z = _float_at(s, i, end)
        i = end
        if i < n and (s[i] == "+" or s[i] == "-"):
            x = z
            end = _float_end(s, i)
            if end != i:
                y = _float_at(s, i, end)
                i = end
            else:
                y = 1.0 if s[i] == "+" else -1.0
                i += 1
            if not (i < n and (s[i] == "j" or s[i] == "J")):
                raise ValueError("complex() arg is a malformed string")
            i += 1
        elif i < n and (s[i] == "j" or s[i] == "J"):
            i += 1
            y = z
        else:
            x = z
    else:
        if i < n and (s[i] == "+" or s[i] == "-"):
            y = 1.0 if s[i] == "+" else -1.0
            i += 1
        else:
            y = 1.0
        if not (i < n and (s[i] == "j" or s[i] == "J")):
            raise ValueError("complex() arg is a malformed string")
        i += 1
    while i < n and _space(s[i]):
        i += 1
    if bracket:
        if not (i < n and s[i] == ")"):
            raise ValueError("complex() arg is a malformed string")
        i += 1
        while i < n and _space(s[i]):
            i += 1
    if i != n:
        raise ValueError("complex() arg is a malformed string")
    return complex(x, y)


def _float_end(s: str, i: int) -> int:
    # where the longest float at s[i:] ends (i if there is none), as PyOS_string_to_double
    # parses one: a sign, then digits with a point and an exponent, or inf, infinity or nan
    n = len(s)
    j = i
    if j < n and (s[j] == "+" or s[j] == "-"):
        j += 1
    k = j
    while k < n and _digit(s[k]):
        k += 1
    digits = k - j
    if k < n and s[k] == ".":
        k += 1
        f = k
        while k < n and _digit(s[k]):
            k += 1
        digits += k - f
    if digits > 0:
        if k < n and (s[k] == "e" or s[k] == "E"):
            e = k + 1
            if e < n and (s[e] == "+" or s[e] == "-"):
                e += 1
            if e < n and _digit(s[e]):
                while e < n and _digit(s[e]):
                    e += 1
                k = e
        return k
    word = s[j : j + 8].lower()
    if word.startswith("infinity"):
        return j + 8
    if word.startswith("inf") or word.startswith("nan"):
        return j + 3
    return i


def _float_at(s: str, i: int, end: int) -> float:
    # the float s[i:end] spells (_float_end's): float() rounds it as _Py_dg_strtod, and reads an
    # infinity or a NaN as _Py_parse_inf_or_nan (a NaN with the sign written)
    return float(s[i:end])
