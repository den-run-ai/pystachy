# pystachy: dynamic-any
# percent_format() of the int range's ends, -2**63 and 2**63 - 1, read at run time: each
# conversion, flag, width and precision formats the signed value, whose magnitude -(-2**63) is
# no int of the range (tests/percent_reference runs CPython's own % for the same cases)
from typing import Any

try:
    from _pystachy_percent import percent_format
except ImportError:
    from percent_oracle import percent_format

lo = int("-9223372036854775808")
hi = int("9223372036854775807")
for v in [lo, hi]:
    cases: list[tuple[str, Any]] = [
        ("%d|%i|%u", (v, v, v)),
        ("%x|%X|%o", (v, v, v)),
        ("%#x|%#X|%#o", (v, v, v)),
        ("%+d|% d|%-25d|%25d|%025d", (v, v, v, v, v)),
        ("%.21d|%25.21d|%-+25.21x|%#030o", (v, v, v, v)),
        ("%(n)d|%(n)x", {"n": v}),
    ]
    for fmt, args in cases:
        try:
            print(repr(percent_format(fmt, args)))
        except (TypeError, ValueError, OverflowError) as e:
            print(fmt, type(e).__name__, e)
