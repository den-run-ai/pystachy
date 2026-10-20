# string.Formatter (lib/string.py, adapted, with _string's parsers in lib/_pystachy_string.py):
# parse(), format(), vformat(), automatic and manual field numbering, conversions, nested
# format specs, arguments of different types (positional ones, or keyword ones), and the
# ValueErrors, IndexErrors and KeyErrors of CPython's parsers and lookups, in order
import string
from string import Formatter

f = Formatter()
for s in ["", "abc", "a{}b", "{0}{1}", "{{x}}", "}}{{", "{a!r:>5}", "{a:{b}}", "{a[1]}", "{0[}]}", "{é}"]:
    print(repr(s), list(f.parse(s)))
for s in ["x{", "x}", "{a", "{a!", "{a!r", "{a!rr}", "{a:{b}", "{a{}", "{!}", "{a:}}"]:
    try:
        print(list(f.parse(s)))
    except ValueError as e:
        print(repr(s), "ValueError:", e)
print([name for text, name, spec, conv in f.parse("{a} and {b!r} {{c}} {}") if name is not None])

print(f.format("{} {}", 1, 2), f.format("{0}-{1}-{0}", "a", "b"), f.format("plain"))
print(f.format("{0!s}|{0!r}|{0!a}|{0:>4}", "é"))
print(f.format("{:>{}}|{:^{w}}|", "x", "5", "y", w="3"))
print(f.format("{0:{1}.{2}f}", 3.14159, 8, 2), f.format("{:08.3f} {:+d} {:x}", 2.5, 7, 255))
print(f.format("{} {!r} {} {:5}", [1, 2], None, True, 2.5))
print(f.format("{name} is {age:>4}", name="Ann", age="31"), f.format("{a}{b}{a}", a="1", b="2"))
d: dict[str, int] = {"n": 3, "m": 4}
none: dict[str, float] = {}
print(f.vformat("{n:03d}/{m}", (), d), f.vformat("{0:.1f} {1!r}", (1.5, 2.25), none))
print(string.Formatter().format("{0} and {1}", "a", "b"))

for bad in ["{0!x}", "{} {1}", "{0} {}", "{0:{1:{2:{3:{4}}}}}", "{", "{2}", "{9}", "{0:{9}}"]:
    try:
        print(f.format(bad, 1, 2, 3, 4, 5))
    except (ValueError, IndexError, KeyError) as e:
        print(repr(bad), type(e).__name__, e)
for bad in ["{missing}", "{0}", "{x!}"]:
    try:
        print(f.format(bad, x=1))
    except (ValueError, IndexError, KeyError) as e:
        print(repr(bad), type(e).__name__, e)
