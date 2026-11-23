"""printf-style formatting of a format string that only the run time knows, for Pystachy.

A subset implementation of CPython 3.13.16's PyUnicode_Format() (Objects/unicodeobject.c), which
`fmt % args` runs: percent_format(fmt, args) is `fmt % args`. It parses and formats as
unicode_format_arg_parse(), unicode_format_arg_format() and unicode_format_arg_output() do, with
CPython's errors in CPython's order. The compiler formats a literal format string itself; the
library modules whose format strings are their callers' (logging's messages and Formatter
formats) call this function, with the arguments as values of `object`
(docs/language/typing.md#object), whatever they hold: a tuple's items, read through its view,
are the arguments, and a dict's values by key.

Limits: only a dict or a list counts as a mapping (CPython's PyMapping_Check() also takes any
object with `__getitem__`), and only ints, bools and floats as numbers (CPython also converts
objects with `__int__`, `__float__` or `__index__`).
"""

__all__ = ["percent_format"]

_F_LJUST = 1
_F_SIGN = 2
_F_BLANK = 4
_F_ALT = 8
_F_ZERO = 16

_PY_SSIZE_T_MAX = 9223372036854775807
_INT_MAX = 2147483647


class _Formatter:
    # PyUnicode_Format()'s state (struct unicode_formatter_t): its arguments, and, of a conversion
    # (struct unicode_format_arg_t), its flags, width, precision and whether it has a sign
    def __init__(self, fmt: str, args: object) -> None:
        self.fmt = fmt
        self.pos = 0
        a: object = args
        self.args: object = a
        if isinstance(a, tuple):
            self.arglen = len(a)
            self.argidx = 0
        else:
            self.arglen = -1
            self.argidx = -2
        self.mapping: object = a
        # (PyMapping_Check(), but for a tuple or a str: here a dict or a list)
        self.has_mapping: bool = isinstance(a, dict) or isinstance(a, list)
        self.flags = 0
        self.width = -1
        self.prec = -1
        self.sign = False

    def next_arg(self) -> object:
        # unicode_format_getnextarg()
        argidx = self.argidx
        if argidx < self.arglen:
            self.argidx = argidx + 1
            a = self.args
            if self.arglen >= 0 and isinstance(a, tuple):
                return a[argidx]
            return a
        raise TypeError("not enough arguments for format string")


def percent_format(fmt: str, args: object) -> str:
    """Return fmt % args: CPython's printf-style formatting (PyUnicode_Format())."""
    ctx = _Formatter(fmt, args)
    out: list[str] = []
    n = len(fmt)
    while ctx.pos < n:
        p = fmt.find("%", ctx.pos)
        if p < 0:
            out.append(fmt[ctx.pos:])
            break
        if p > ctx.pos:
            out.append(fmt[ctx.pos:p])
        ctx.pos = p + 1
        _format_arg(ctx, out)
    if ctx.argidx < ctx.arglen and not ctx.has_mapping:
        raise TypeError("not all arguments converted during string formatting")
    return "".join(out)


def _format_arg(ctx: _Formatter, out: list[str]) -> None:
    # unicode_format_arg(): one conversion, at ctx.pos, just past its '%'
    fmt = ctx.fmt
    n = len(fmt)
    if ctx.pos < n and fmt[ctx.pos] == "%":
        ctx.pos += 1
        out.append("%")
        return
    ctx.flags = 0
    ctx.width = -1
    ctx.prec = -1
    ctx.sign = False
    ch = _parse_arg(ctx)
    s = _format_value(ctx, ch)
    out.append(_output(ctx, ch, s))
    if ctx.has_mapping and ctx.argidx < ctx.arglen:
        raise TypeError("not all arguments converted during string formatting")


def _parse_arg(ctx: _Formatter) -> str:
    # unicode_format_arg_parse(): the mapping key, flags, width, precision and length modifier,
    # and the conversion character, which it returns
    fmt = ctx.fmt
    n = len(fmt)
    if ctx.pos < n and fmt[ctx.pos] == "(":
        if not ctx.has_mapping:
            raise TypeError("format requires a mapping")
        ctx.pos += 1
        keystart = ctx.pos
        pcount = 1
        while pcount > 0 and ctx.pos < n:
            c = fmt[ctx.pos]
            if c == ")":
                pcount -= 1
            elif c == "(":
                pcount += 1
            ctx.pos += 1
        if pcount > 0:
            raise ValueError("incomplete format key")
        key = fmt[keystart:ctx.pos - 1]
        mapping = ctx.mapping
        if isinstance(mapping, list):
            raise TypeError("list indices must be integers or slices, not str")
        if isinstance(mapping, dict):
            ctx.args = mapping[key]
        ctx.arglen = -1
        ctx.argidx = -2
    while ctx.pos < n:
        c = fmt[ctx.pos]
        if c == "-":
            ctx.flags |= _F_LJUST
        elif c == "+":
            ctx.flags |= _F_SIGN
        elif c == " ":
            ctx.flags |= _F_BLANK
        elif c == "#":
            ctx.flags |= _F_ALT
        elif c == "0":
            ctx.flags |= _F_ZERO
        else:
            break
        ctx.pos += 1
    if ctx.pos < n and fmt[ctx.pos] == "*":
        v = ctx.next_arg()
        if not _is_int(v):
            raise TypeError("* wants int")
        w = int(v)
        if w < 0:
            ctx.flags |= _F_LJUST
            w = -w
        ctx.width = w
        ctx.pos += 1
    elif ctx.pos < n and "0" <= fmt[ctx.pos] <= "9":
        w = 0
        while ctx.pos < n and "0" <= fmt[ctx.pos] <= "9":
            d = ord(fmt[ctx.pos]) - 48
            if w > (_PY_SSIZE_T_MAX - d) // 10:
                raise ValueError("width too big")
            w = w * 10 + d
            ctx.pos += 1
        ctx.width = w
    if ctx.pos < n and fmt[ctx.pos] == ".":
        ctx.prec = 0
        ctx.pos += 1
        if ctx.pos < n and fmt[ctx.pos] == "*":
            v = ctx.next_arg()
            if not _is_int(v):
                raise TypeError("* wants int")
            p = int(v)
            if p > _INT_MAX or p < -_INT_MAX - 1:
                raise OverflowError("Python int too large to convert to C int")
            ctx.prec = p if p >= 0 else 0
            ctx.pos += 1
        elif ctx.pos < n and "0" <= fmt[ctx.pos] <= "9":
            p = 0
            while ctx.pos < n and "0" <= fmt[ctx.pos] <= "9":
                d = ord(fmt[ctx.pos]) - 48
                if p > (_INT_MAX - d) // 10:
                    raise ValueError("precision too big")
                p = p * 10 + d
                ctx.pos += 1
            ctx.prec = p
    if ctx.pos < n and (fmt[ctx.pos] == "h" or fmt[ctx.pos] == "l" or fmt[ctx.pos] == "L"):
        ctx.pos += 1
    if ctx.pos >= n:
        raise ValueError("incomplete format")
    ch = fmt[ctx.pos]
    ctx.pos += 1
    return ch


def _is_int(v: object) -> bool:
    # is v an int (a bool too), tested apart from its readers, which read it as the value of
    # object it is: one that holds an int past 64 bits stays one (int(), str(), format())
    return isinstance(v, int)


def _is_float(v: object) -> bool:
    return isinstance(v, float)


def _is_bool(v: object) -> bool:
    return isinstance(v, bool)


def _is_str(v: object) -> bool:
    return isinstance(v, str)


def _format_value(ctx: _Formatter, ch: str) -> str:
    # unicode_format_arg_format(): the text of the next argument by conversion ch
    v = ctx.next_arg()
    if ch == "s" or ch == "r" or ch == "a":
        if ch == "s":
            return str(v)
        if ch == "r":
            return repr(v)
        return ascii(v)
    if ch == "i" or ch == "d" or ch == "u" or ch == "o" or ch == "x" or ch == "X":
        ctx.sign = True
        return _format_long(ctx, v, ch)
    if ch == "e" or ch == "E" or ch == "f" or ch == "F" or ch == "g" or ch == "G":
        ctx.sign = True
        return _format_float(ctx, v, ch)
    if ch == "c":
        return _format_char(v)
    c = ord(ch)
    shown = ch if 31 <= c <= 126 else "?"
    raise ValueError(f"unsupported format character '{shown}' ({hex(c)}) at index {ctx.pos - 1}")


def _format_long(ctx: _Formatter, v: object, ch: str) -> str:
    # mainformatlong() and _PyUnicode_FormatLong(): "-"? ("0x" | "0X" | "0o")? digit+, with at
    # least the precision's digits
    if not _is_int(v) and not _is_float(v):
        if ch == "o" or ch == "x" or ch == "X":
            raise TypeError(f"%{ch} format: an integer is required, not {type(v).__name__}")
        raise TypeError(f"%{ch} format: a real number is required, not {type(v).__name__}")
    if _is_float(v):
        if ch == "o" or ch == "x" or ch == "X":
            raise TypeError(f"%{ch} format: an integer is required, not float")
        iv: object = int(v)
    elif _is_bool(v):
        iv = 1 if v else 0
    else:
        iv = v
    # the digits of the signed value, less its "-": the magnitude of the least int, -(-2**63),
    # would not be an int of the range
    if ch == "o":
        digits = format(iv, "o")
        prefix = "0o"
    elif ch == "x" or ch == "X":
        digits = format(iv, "x")
        prefix = "0x"
    else:
        digits = str(iv)
        prefix = ""
    neg = digits.startswith("-")
    if neg:
        digits = digits[1:]
    if ctx.prec > len(digits):
        digits = "0" * (ctx.prec - len(digits)) + digits
    s = ("-" if neg else "") + (prefix if ctx.flags & _F_ALT else "") + digits
    if ch == "X":
        s = s.upper()
    return s


def _format_float(ctx: _Formatter, v: object, ch: str) -> str:
    # formatfloat(): PyFloat_AsDouble(), then PyOS_double_to_string(), which format() also runs
    if not _is_float(v) and not _is_int(v):
        raise TypeError(f"must be real number, not {type(v).__name__}")
    x = float(v)
    prec = ctx.prec if ctx.prec >= 0 else 6
    return format(x, ("#" if ctx.flags & _F_ALT else "") + "." + str(prec) + ch)


def _format_char(v: object) -> str:
    # formatchar(): a str of one character, or an int that is a code point (its digits first,
    # which tell one past the code points' range without an int past 64 bits)
    if _is_str(v):
        s = str(v)
        if len(s) == 1:
            return s
        raise TypeError("%c requires int or char")
    if not _is_int(v):
        raise TypeError("%c requires int or char")
    if _is_bool(v):
        return chr(1 if v else 0)
    digits = str(v)
    if len(digits) > 8:
        raise OverflowError("%c arg not in range(0x110000)")
    c = int(digits)
    if c < 0 or c > 0x10FFFF:
        raise OverflowError("%c arg not in range(0x110000)")
    return chr(c)


def _output(ctx: _Formatter, ch: str, s: str) -> str:
    # Padding reads only the settings of this conversion, after value formatting has run.
    return _pad_output(ctx.flags, ctx.sign, ctx.width, ctx.prec, ch, s)


def _pad_output(flags: int, sign: bool, width: int, prec: int, ch: str, s: str) -> str:
    # unicode_format_arg_output(): s with the precision (of a str), the sign and the width
    fill = "0" if sign and flags & _F_ZERO else " "
    length = len(s)
    if ((width == -1 or width <= length) and (prec == -1 or prec >= length)
            and not flags & (_F_SIGN | _F_BLANK)):
        return s
    if (ch == "s" or ch == "r" or ch == "a") and prec >= 0 and length > prec:
        length = prec
    pindex = 0
    signchar = ""
    if sign:
        c = s[0]
        if c == "-" or c == "+":
            signchar = c
            length -= 1
            pindex = 1
        elif flags & _F_SIGN:
            signchar = "+"
        elif flags & _F_BLANK:
            signchar = " "
        else:
            sign = False
    if width < length:
        width = length
    parts: list[str] = []
    if sign:
        if fill != " ":
            parts.append(signchar)
        if width > length:
            width -= 1
    alt = (flags & _F_ALT) != 0 and (ch == "x" or ch == "X" or ch == "o")
    if alt:
        if fill != " ":
            parts.append(s[pindex:pindex + 2])
            pindex += 2
        width -= 2
        if width < 0:
            width = 0
        length -= 2
    if width > length and not flags & _F_LJUST:
        parts.append(fill * (width - length))
        width = length
    if fill == " ":
        if sign:
            parts.append(signchar)
        if alt:
            parts.append(s[pindex:pindex + 2])
            pindex += 2
    if length > 0:
        parts.append(s[pindex:pindex + length])
    if width > length:
        parts.append(" " * (width - length))
    return "".join(parts)
