# pystachy: python-int
# Adapted from CPython 3.13.16 Lib/test/test_int.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# 2d947888f306e945ebc12c6817691330528c0bc7a13330b942c9af97fe3075d8.
# PSF License v2: tests/upstream/CPYTHON-LICENSE.txt; THIRD_PARTY_NOTICES.
# Pystachy port: selected IntTestCases.test_basic (all base 2..36 spellings
# of 2**32+1, prefix checks, whitespace/sign cases), test_invalid_signs,
# test_unicode, test_underscores's explicit string cases and test_int_base_limits.
# Keep builtin int(); replace unittest with assertions/caught exceptions,
# and expected values with decimal strings. Exclude floats, bytes, buffer and
# subclass inputs, C-API behavior, indexable bases and giant base values.
spellings = [
    "100000000000000000000000000000001", "102002022201221111212", "10000000000000001",
    "32244002423142", "1550104015505", "211301422355", "40000000001", "12068657455",
    "4294967297", "1904440555", "9ba461595", "535a7988a", "2ca5b7465", "1a20dcd82",
    "100000001", "a7ffda92", "704he7g5", "4f5aff67", "3723ai4h", "281d55i5",
    "1fj8b185", "1606k7id", "mb994ah", "hek2mgm", "dnchbnn", "b28jpdn", "8pfgih5",
    "76beigh", "5qmcpqh", "4q0jto5", "4000001", "3aokq95", "2qhxjlj", "2br45qc", "1z141z5",
]
for i in range(len(spellings)):
    assert str(int(spellings[i], i + 2)) == "4294967297"
    assert int("0", i + 2) == 0
print("all bases", len(spellings))

for s in ["314", " 314", "314 ", " \t\t 314 \t\t "]:
    assert str(int(s)) == "314"
for s in ["-3", " -3 ", "\u2003-3\u2002"]:
    assert str(int(s)) == "-3"
assert str(int("१२३४५६७८९०1234567890")) == "12345678901234567890"
assert str(int("١٢٣٤٥٦٧٨٩٠")) == "1234567890"
assert str(int("१२३४५६७८९०1234567890", 0)) == "12345678901234567890"
assert str(int("١٢٣٤٥٦٧٨٩٠", 0)) == "1234567890"
assert str(int("1_00", 3)) == "9"
assert str(int("0_100")) == "100"
assert str(int("0x_ffffffffffffffff", 0)) == "18446744073709551615"
assert str(int("-0b_1_000", 0)) == "-8"
assert str(int("+0o_7_77", 0)) == "511"
assert str(int("000_0", 0)) == "0"
assert str(int("100", base=2)) == "4"
assert str(int()) == "0"
print("valid parsing and Unicode passed")

errors = 0
for s in ["", " ", " \t\t ", "+", "-", "- 1", "+ 1", " + 1 ", "_100", "+_100",
          "1__00", "100_", "1\x002", "\u0200", "  1x", "0x", "0x_", "0x__1", "0b2",
          "0b02", "0o8", "0o08", "0xg", "0x0g", "010", "0_1"]:
    try:
        int(s, 0)
    except ValueError:
        errors += 1
for base in [1, 37, -909]:
    try:
        int("0", base)
    except ValueError as exc:
        print(exc)
        errors += 1
assert errors == 29
print("invalid parse cases", errors)

# Original bool-as-int boundary coverage; CPython int(False/True) is 0/1.
for value in [False, True]:
    number = int(value)
    expected = int(value)
    assert str(number) == str(expected) and repr(number) == str(expected)
    assert int(number) == expected and number == expected
    assert number == value and bool(number) == value
    assert hash(number) == hash(expected)
print("boolean construction and conversion passed")
