# pystachy: python-int
# int() of text with promoting ints (docs/python-int.md): CPython's parser reads to a NUL, with
# whitespace before it, so digits past the limit are reported before what follows the NUL. Any
# other character after the digits is an invalid literal first.
def show(s: str, base: int) -> None:
    try:
        print(ascii(s[:6]), ascii(s[-4:]), len(s), base, int(s, base))
    except ValueError as e:
        m = str(e)
        print(ascii(s[:6]), ascii(s[-4:]), len(s), base, "ValueError", ascii(m[:72]), len(m))


z = "0" * 4300
for t, base in [(z + "7\x00", 10), (z + "7 \x00", 10), (z + "7\t\n\x00x", 10), (z + "2\x00 ", 3), (z + "1\x00", 0), ("-" + z + "7\x00", 10),
                (z + "7x", 10), (z + "7 x", 10), (z + "7_\x00", 10), (z + "7_", 10), (z + "7\x00", 16), (z + "7", 16), (z[1:] + "7\x00", 10),
                (z[1:] + "7", 10), ("12\x00", 10), ("12 \x00", 10), ("12\x0034", 10), ("\x00", 10), ("0x1f\x00", 0), ("9" * 30 + "\x00", 10), ("9" * 30, 10)]:
    show(t, base)
