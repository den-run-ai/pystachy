# Selected assertions adapted from CPython 3.13.16 Lib/test/test_str.py,
# StrTest.test_iteration, test_iterators, test_find, test_rfind, test_count,
# test_index and test_rindex; and Lib/test/string_tests.py,
# StringLikeTest.test_extended_getslice and BaseTest.test_find/test_rfind/test_count.
# Source commit: cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# unittest scaffolding becomes assertions; this is a selected regression subset,
# not an unchanged upstream suite. The slice matrix uses explicit character lists
# as its independent reference and adds mixed-width, combining and NUL cases.
# Bounds/iterator additions exercise the same APIs through compiler lowering.
# Excludes subclass checks, wrong-type calls rejected at compile time, arbitrary
# precision indices, lone surrogates, normalization and Unicode case tables.


def test_characters(s: str, chars: list[str]) -> None:
    assert len(s) == len(chars)
    assert list(s) == chars
    assert tuple(s) == tuple(chars)
    assert [c for c in s] == chars
    assert [c for c in reversed(s)] == chars[::-1]
    assert [c for i, c in enumerate(s)] == chars
    assert [i for i, c in enumerate(s)] == list(range(len(chars)))
    assert [a + b for a, b in zip(s, s)] == [c + c for c in chars]
    assert "".join(iter(s)) == s
    for i in range(len(chars)):
        assert s[i] == chars[i]
        assert s[i - len(chars)] == chars[i]
        assert ord(s[i]) == ord(chars[i])
    for i in [-9223372036854775808, -100, -len(chars) - 1, len(chars),
              100, 9223372036854775807]:
        try:
            s[i]
        except IndexError:
            pass
        else:
            assert False, "index must raise IndexError"
    # Retain upstream's comparison against list slicing, but do not construct
    # that list from s: an equally broken iterator would hide slicing failures.
    bounds: list[int | None] = [None, -100, -3, -1, 0, 1, 3, 100]
    steps: list[int | None] = [None, -100, -3, -1, 1, 2, 3, 100]
    checks = 0
    for start in bounds:
        for stop in bounds:
            assert s[start:stop] == "".join(chars[start:stop])
            for step in steps:
                assert s[start:stop:step] == "".join(chars[start:stop:step])
                checks += 1
    assert s[::9223372036854775807] == "".join(chars[::9223372036854775807])
    assert s[::-9223372036854775808] == "".join(chars[::-9223372036854775808])
    assert s[-9223372036854775808:9223372036854775807] == s
    try:
        s[::0]
    except ValueError:
        pass
    else:
        assert False, "zero slice step must raise ValueError"
    print("characters", len(chars), checks)


def test_upstream_iteration() -> None:
    # test_str.StrTest.test_iteration and test_iterators (iter() spelling).
    for case in ["abc", "🚀🚀🚀", "\u1111\u2222\u3333"]:
        assert case == "".join(iter(case))
    it = iter("\u1111\u2222\u3333")
    assert next(it) == "\u1111"
    assert next(it) == "\u2222"
    assert next(it) == "\u3333"
    try:
        next(it)
    except StopIteration:
        pass
    else:
        assert False, "string iterator must be exhausted"
    print("upstream iteration", 7)


def test_upstream_search() -> None:
    # Exact non-ASCII character/substring cases from StrTest.test_find/rfind.
    finds = [
        ("тест", "т", 0, 4, 0), ("тест", "т", 1, 4, 3),
        ("тест", "т", 1, 3, -1), ("тест", "e", 0, 4, -1),
        ("тест тест", "ес", 0, 9, 1), ("тест тест", "ес", 1, 9, 1),
        ("тест тест", "ес", 1, 3, 1), ("тест тест", "ес", 2, 9, 6),
        ("тест тест", "ес", 6, 7, -1), ("тест тест", "ес", 7, 9, -1),
        ("тест тест", "ec", 0, 9, -1),
    ]
    rfinds = [
        ("тест", "е", 0, 4, 1), ("тест", "е", 1, 4, 1),
        ("тест", "е", 2, 4, -1), ("тест", "e", 0, 4, -1),
        ("тест тест", "ес", 0, 9, 6), ("тест тест", "ес", 1, 9, 6),
        ("тест тест", "ес", 1, 3, 1), ("тест тест", "ес", 2, 9, 6),
        ("тест тест", "ес", 6, 7, -1), ("тест тест", "ес", 7, 9, -1),
        ("тест тест", "ec", 0, 9, -1),
    ]
    for s, needle, start, end, expected in finds:
        assert s.find(needle, start, end) == expected
    for s, needle, start, end, expected in rfinds:
        assert s.rfind(needle, start, end) == expected
    # Exact mixed-kind assertions, factored to share repeated input patterns.
    for wide, narrow in [("\u0102", "a"), ("\U00100304", "a"),
                         ("\U00100304", "\u0102")]:
        assert (wide * 100 + narrow).find(narrow) == 100
        assert (wide * 100 + narrow).index(narrow) == 100
        assert (narrow + wide * 100).rfind(narrow) == 0
        assert (narrow + wide * 100).rindex(narrow) == 0
        assert (wide + narrow * 10).count(narrow) == 10
        assert (narrow * 100).find(wide) == -1
        assert (narrow * 100).rfind(wide) == -1
        assert (narrow * 10).count(wide) == 0
        assert (wide * 100 + narrow + "_").find(narrow + "_") == 100
        assert (wide * 100 + narrow + "_").index(narrow + "_") == 100
        assert ("_" + narrow + wide * 100).rfind("_" + narrow) == 0
        assert ("_" + narrow + wide * 100).rindex("_" + narrow) == 0
        assert (wide + (narrow + "_") * 10).count(narrow + "_") == 10
    print("upstream search", len(finds) + len(rfinds) + 39)


def search_bounds(s: str, needle: str, start: int, end: int) -> None:
    # The recording is the CPython oracle for the complete results, including
    # empty needles, oversized/reversed bounds and non-overlapping counts.
    first = s.find(needle, start, end)
    last = s.rfind(needle, start, end)
    count = s.count(needle, start, end)
    prefix = s.startswith(needle, start, end)
    suffix = s.endswith(needle, start, end)
    try:
        index = s.index(needle, start, end)
    except ValueError:
        assert first == -1
    else:
        assert first >= 0 and index == first
    try:
        rindex = s.rindex(needle, start, end)
    except ValueError:
        assert last == -1
    else:
        assert last >= 0 and rindex == last
    if first >= 0:
        assert s[first:first + len(needle)] == needle
    if last >= 0:
        assert s[last:last + len(needle)] == needle
    print(first, last, count, prefix, suffix)


def test_boundaries() -> None:
    # Equivalent text patterns exercise ASCII and 2/3/4-byte characters; the
    # combining mark is a separate code point, and embedded NUL is not an end.
    for s in ["", "ababa", "é中🚀é中", "e\u0301e\u0301", "é\0中é"]:
        for needle in ["", "a", "é", "中", "🚀", "é中", "\u0301", "\0"]:
            for start, end in [(-100, 100), (0, 0), (0, 1), (0, 3),
                               (1, 4), (-3, -1), (3, 1), (5, 5),
                               (6, 100), (100, 100)]:
                search_bounds(s, needle, start, end)
    s = "é中🚀é中"
    print(s.startswith(("x", "中🚀"), 1, 3), s.endswith(("x", "🚀é"), 1, 4))
    print(s.startswith(("", "é"), 6), s.endswith(("", "é"), 6))
    print(s.find("é"), s.rfind("é"), s.index("中"), s.rindex("中"), s.count(""))
    print(s.find("é", -2), s.rfind("é", 1), s.count("", 2))
    search_bounds(s, "", -9223372036854775808, 9223372036854775807)
    search_bounds(s, "中", -9223372036854775808, 9223372036854775807)
    search_bounds(s, "", 9223372036854775807, 9223372036854775807)


def test_ord_chr() -> None:
    points = [0, 0x7f, 0x80, 0xff, 0x100, 0x7ff, 0x800, 0xd7ff,
              0xe000, 0xffff, 0x10000, 0x1f680, 0x10ffff]
    for cp in points:
        c = chr(cp)
        assert len(c) == 1
        assert ord(c) == cp
        assert list(c) == [c]
    for cp in [-1, 0x110000]:
        try:
            chr(cp)
        except ValueError:
            pass
        else:
            assert False, "invalid chr must raise ValueError"
    for s in ["", "éx", "e\u0301"]:
        try:
            ord(s)
        except TypeError:
            pass
        else:
            assert False, "multiple code points must raise TypeError"
    print("ord/chr", len(points) + 5)


def test_append_cache(parts: list[str]) -> None:
    s = ""
    for i in range(len(parts)):
        assert len(s) == i
        s += parts[i]
        assert len(s) == i + 1
        assert s[-1] == parts[i]
        assert list(s) == parts[:i + 1]
    # The old value remains live across an append; its cached character length
    # and backing data must survive whether the compiler copies or reuses s.
    alias = s
    before = len(alias)
    s += "🚀"
    assert len(s) == before + 1
    assert len(alias) == before
    assert list(alias) == parts
    assert s[:-1] == alias
    print("append cache", before, len(s), len(alias))


def unpack_pair(s: str) -> tuple[str, str]:
    a, b = s
    return a, b


def test_unpack() -> None:
    assert unpack_pair("éA") == ("é", "A")
    a, *middle, z = "é中🚀A"
    assert a == "é" and middle == ["中", "🚀"] and z == "A"
    a, *rest = "é"
    assert a == "é" and rest == []
    for s in ["", "é", "éA🚀"]:
        try:
            unpack_pair(s)
        except ValueError as e:
            print("unpack ValueError:", e)
        else:
            assert False, "wrong unpack arity must raise ValueError"
    print("unpack", a, middle, z)


test_characters("", [])
test_characters("ascii", ["a", "s", "c", "i", "i"])
test_characters("éñß", ["é", "ñ", "ß"])
test_characters("日本語", ["日", "本", "語"])
test_characters("🚀😀", ["🚀", "😀"])
test_characters("aé中🚀e\u0301\0z", ["a", "é", "中", "🚀", "e", "\u0301", "\0", "z"])
test_upstream_iteration()
test_upstream_search()
test_boundaries()
test_ord_chr()
test_append_cache(["a", "b", "é", "中", "🚀", "\0", "e", "\u0301"])
test_append_cache(["🚀", "é", "a", "b", "中"])
test_unpack()
# Former tests/deviations/str_slice_step_bytes.py: UTF-8 sequences stay intact.
s = "añb"
r = s[::-1]
print(len(s), len(r), r == "".join(reversed(s)), r[::-1] == s, r[0] == "b", r[-1] == "a")
print(s[::2], s[1:3:1], s[::3])
# Literal folding must agree with runtime arguments.
print(len("é中🚀"), "é中🚀"[1], "é中🚀"[::-1], ord("🚀"), len(chr(233)))
