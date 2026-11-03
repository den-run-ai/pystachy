# pystachy: dynamic-any
# lib/_pystachy_percent.py's percent_format(fmt, args), printf-style formatting of a format string
# known only at run time (logging's messages and formats), is fmt % args: CPython runs the
# operator itself (tests/percent_reference), and both print each result or error
from typing import Any

try:
    from _pystachy_percent import percent_format
except ImportError:
    from percent_oracle import percent_format


class P:
    def __repr__(self) -> str:
        return "Pé()"

    def __str__(self) -> str:
        return "p-str"


cases: list[tuple[str, Any]] = [
    ("plain", ()),
    ("%s|%r|%a", ("a", "bé", "cé")),
    ("%s %r %a", (P(), P(), P())),
    ("%d|%i|%u|%5d|%-5d|%05d|%+d|% d|%+05d|%-+6d|", (42, -42, 7, 42, 42, -42, 7, 7, 7, -7)),
    ("%.3d|%.0d|%10.4d|%-10.4d|%010.4d", (5, 0, -5, 5, 5)),
    ("%x|%X|%o|%#x|%#X|%#o|%#5x|%#05x|%-#7o|", (255, 255, 8, 255, 255, 8, 10, 10, 8)),
    ("%x %o %#x %#o", (-255, -8, -255, -8)),
    ("%d %s %r %x", (True, True, False, True)),
    ("%d %i", (3.99, -2.5)),
    ("%e|%E|%f|%F|%g|%G", (12345.678, 0.000123, 1.5, -2.25, 1e-5, 3e20)),
    ("%.0e|%.2f|%10.3f|%-10.1f|%+.1f|% .2f|%010.2f|%#.0f|%#g|%.10g", (1.5, 2.675, 3.14159, 2.5, 1.0, 1.0, -3.5, 2.0, 1.0, 1.0 / 3.0)),
    ("%f %F %e %g", (float("inf"), float("-inf"), float("nan"), -0.0)),
    ("%f %e", (3, True)),
    ("%c%c%c|%3c|%-3c|", ("x", 65, True, "y", 0x263A)),
    ("%.2s|%5s|%-5s|%5.1s|%.0s|%r", ("abcdef", "ab", "ab", "xyz", "q", "it's")),
    ("%*d|%-*d|%.*f|%*.*f|%*s", (4, 9, 4, 9, 2, 3.14159, 8, 3, 2.5, -6, "ab")),
    ("%%|%5%|", ()),
    ("%(a)s and %(b)r, %(a)05d", {"a": 1, "b": "two"}),
    ("%(x(y))s", {"x(y)": "nested"}),
    ("%s", [1, "two", None]),
    ("%s", {"k": [1, 2]}),
    ("%s %s", ({"k": 1}, [2])),
    ("%s", (None,)),
    ("%s", ((1, 2),)),
    ("no conversions", {}),
    ("no conversions", []),
    ("%s and %(a)s", {"a": 5}),
    ("%hd %ld %Ld %lf", (1, 2, 3, 4.5)),
    ("%d", 7),
    ("%r", "single"),
    ("%d %d", (1,)),
    ("%s", ()),
    ("%d", ("x",)),
    ("%i", (None,)),
    ("%x", (1.5,)),
    ("%X", ("s",)),
    ("%f", ("1.5",)),
    ("%c", ("ab",)),
    ("%c", (1.5,)),
    ("%c", (0x110000,)),
    ("%c", (-1,)),
    ("%*d", ("4", 1)),
    ("%.*f", (1.5, 2.0)),
    ("%z", (1,)),
    ("%é", (1,)),
    ("abc%", ()),
    ("%5", (1,)),
    ("%.", (1,)),
    ("%(a", {"a": 1}),
    ("%(a)", {"a": 1}),
    ("%(a)s", (1,)),
    ("%(missing)s", {"a": 1}),
    ("%(a)s", [1]),
    ("abc", 5),
    ("abc", "s"),
    ("abc", (1,)),
    ("%s %s", [1]),
    ("%d", float("inf")),
    ("%d", float("nan")),
    ("%99999999999999999999d", (1,)),
    ("%.99999999999d", (1,)),
]
for fmt, args in cases:
    try:
        print(repr(percent_format(fmt, args)))
    except (TypeError, ValueError, OverflowError, KeyError) as e:
        print(type(e).__name__ + ":", e)
