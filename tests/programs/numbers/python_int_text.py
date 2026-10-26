# pystachy: python-int
# Promoting ints (docs/python-int.md): literals past 64 bits in every base, int() of text, and text
# of ints, as CPython gives them.

print(123456789012345678901234567890, -98765432109876543210, 1_000_000_000_000_000_000_000)
print(0xFFFFFFFFFFFFFFFF, 0x1_0000_0000_0000_0000, -0x8000000000000001, 0o1777777777777777777777)
print(0b1_0000000000000000000000000000000000000000000000000000000000000000, -0B11 << 70)
print(9223372036854775807, -9223372036854775808, 9223372036854775808, -9223372036854775809)
big = 2 ** 200
print(str(big), repr(-big), f"{big}", f"[{-big}]", f"{big!r}", str(big - big), len(str(big)))
print(int("123456789012345678901234567890"), int("-0x1fffffffffffffffff", 16), int("  +42  "))
print(int("0b" + "1" * 80, 0), int("zz" * 10, 36), int("1_000_000_000_000_000_000_000"), int("077", 8))
print(int("٣٤٥٦٧٨٩٠١٢٣٤٥٦٧٨٩٠١٢٣"), int(str(big)) == big, int(repr(-big)) == -big)
print(int(1e30), int(-2.5e19), int(3.99), int(-3.99), int(2.0 ** 100), int(-(2.0 ** 70)))
print(float(big), float(-(2 ** 63) - 1), float(2 ** 64 - 1), float((2 ** 53 - 1) * 2 ** 971), float(2 ** 54 - 1), float(2 ** 54 + 3))
print(str(2 ** 63) + "!", "x" + str(-(2 ** 64)), "%s and %s" % (2 ** 3, 4))
for text, base in [("abc", 10), ("12a", 10), ("", 10), ("0x10", 10), ("99", 8), ("1__0", 10), ("_1", 10)]:
    try:
        print(int(text, base))
    except ValueError as e:
        print("ValueError:", e)
try:
    print(int("10", 37))
except ValueError as e:
    print("ValueError:", e)


def to_float(v: int) -> None:
    try:
        print(float(v))
    except OverflowError as e:
        print("OverflowError:", e)


to_float(2 ** 1024)
to_float(2 ** 1024 - 2 ** 970)
to_float(-(2 ** 1100))
to_float(2 ** 1024 - 2 ** 971)
try:
    print(int(float("inf")))
except OverflowError as e:
    print("OverflowError:", e)
try:
    print(int(float("nan")))
except ValueError as e:
    print("ValueError:", e)
try:
    print(str(10 ** 4300))
except ValueError as e:
    print("ValueError:", str(e)[:45])
print(len(str(10 ** 4299)), hash(2 ** 61 - 1), hash(-(2 ** 61) + 1), hash(2 ** 61), hash(-1), hash(2 ** 64) == hash(2 ** 64 % (2 ** 61 - 1)))
