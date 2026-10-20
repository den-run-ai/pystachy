# String literals and f-strings: escapes (\x, \u, \U, octal, as UTF-8), raw strings, implicit
# concatenation, f-string = specifier, conversions, nested format specs, __format__

x = 5
print(f"\x7bx\x7d", f"{x}\x7b")

print("\U00000041", "\u00e9t\u00e9", "caf\xe9", "\101\351", len("\x41"))

m = -9223372036854775807 - 1
print(repr("abc"[:m]), repr("abc"[m:]), [1, 2][m:1])

x = 1
print("a" f"{x}" "b" f"{x + 1}")

print(r"a\"b", r"\n", len(r"\n"))

x = 1
print(f"{ x }", f"{ x + 1 = }", f"{x=}", f"{x = :>4}", f"{x=!s}", f"{3.14159=:.2f}")

class P:
    def __str__(self) -> str:
        return "S"

    def __repr__(self) -> str:
        return "R"


class F:
    def __format__(self, spec: str) -> str:
        return "F" + spec

    def __str__(self) -> str:
        return "S"


p = P()
w = 6
xf = 3.14159
print(f"{p!a} {p=} {xf!s:.3} [{p!s:>3}] {'é'!a} {ascii('caf' + chr(233))}")
print(f"{F()}", f"{F():}", f"{F():>5}", f"[{xf:.{w - 4}f}]", f"[{'ab':>{w}}]", f"{'\n'.join(['a', 'b'])}")
print(f"{None!r:>6}|{None}")
print(f"{w, xf}", f"{w, xf = }", f"{w, -w!r:>9}")
