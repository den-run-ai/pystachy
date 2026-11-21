# int(s, base): a sign, a prefix that the base allows, digits below the base with single
# underscores between them, and whitespace around them; base 0 reads the base from the prefix,
# and then only 0 may begin with a 0. The digits and spaces of other scripts count; a NUL ends
# the text. CPython's checks, in its order
def show(s: str, base: int) -> None:
    try:
        print(ascii(s[:14]), len(s), base, int(s, base))
    except ValueError as e:
        m = str(e)
        print(ascii(s[:14]), len(s), base, "ValueError", ascii(m[:72]), len(m))


for t in ["0", "-0", "+0", "7", "-7", "+7", "+-7", "--7", "+ 7", "- 7", "", " ", "+", "-", "_", "1_2", "_12", "12_", "1__2", "1_2_3",
          " 12 ", "\t\n12\r\x0b\x0c", "1 2", "12\x00", "12 \x00", "12\x00 ", "\x0012", "\x00", "12\x1c", "12.0", "1e3", "0x1f", "1f", "²"]:
    show(t, 10)
for t in ["0", "00", "0_0", "-00", "07", "0_7", "007", "10", "0x1F", "0X_1f", "0x_", "0x", "0x__1", "0_x1", "-0b101", "+0o17", "0B_1_0",
          "0b2", "0o8", "0xg", "0b", "0o", " 0x10 ", "0x 10", "1_000", "0b1\x00", "٠١٢", "٠٧"]:
    show(t, 0)
for t, base in [("0b1", 36), ("0x", 36), ("0o7", 36), ("0b1", 2), ("0b1", 16), ("0x1", 2), ("0x1", 16), ("0o7", 8), ("0o7", 16), ("2", 2),
                ("1_0", 2), ("g", 16), ("G", 17), ("z", 36), ("Z", 35), ("zZ", 36), ("-zz", 36), ("12", 3), ("13", 3), ("10", 1), ("10", 37),
                ("10", -1), ("x", 1), ("", 99), ("_0b1", 2), ("0b_1", 2), ("0b__1", 2), ("0_b1", 2)]:
    show(t, base)
# digits and spaces of other scripts, which become ASCII before the number is read
for t in ["٣٤", "-१२३", "１２３", " 12 ", "1２3", "𝟗𝟖", "٣_٤", "٣٤x", "é", "12é", "1 2", "٣\x00", "٣٤" * 3, "x" * 250, "'\"" * 120,
          "é" * 150 + "x" * 150]:
    show(t, 10)
show("ｆ", 16)
show("٧٧", 8)
show("٨", 8)
# 4300 digits at most, in a base that is no power of two: digits alone count, the text is
# checked first, but for a NUL that ends it
z = "0" * 4300
for t, base in [(z, 10), (z + "7", 10), (z[1:] + "7", 10), (z + "7", 16), (z + "7", 32), (z + "7", 3), ("0b" + z + "1", 0), (z + "7x", 10),
                (z + "7_", 10), (z + "7 x", 10), (z + "7\x00", 10), (z + "7 \x00", 10), (z[2:] + "1_2", 10), (" -" + z[1:] + " ", 10),
                (z + "٧", 10), (z, 0), (z + "0", 0), (z + "1", 0), (z[2:] + "1", 0)]:
    show(t, base)
