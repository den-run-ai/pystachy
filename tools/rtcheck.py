"""Differential fuzzing of runtime.py on CPython, against CPython's own str methods and math
(and the dict hash functions against the formulas runtime.c used, on unsigned 64-bit ints).

runtime.py is ordinary Python, so CPython runs it, with tools/rt_cpython/_rt.py standing in for
the compiler's primitives: each pys_* function is called directly and compared with what CPython
computes, on random inputs, with no compilation. Strs are ASCII here (where Pystachy behaves exactly
as CPython) plus UTF-8 text for the width methods, which count characters; a Pystachy str is
given as its bytes, one character per byte. 64-bit overflow is not tested here (CPython's ints
grow): the differential tests compile the same code and check it.

The format functions get runtime.c's pys_fmt_float (float digits by snprintf) from CPython's own
float formatting, which it reproduces.

usage: python3 tools/rtcheck.py [N] [SEED]   (N rounds of cases, default 5000)
"""
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tools", "rt_cpython"), ROOT]
import runtime as rt  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
R = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
ASCII = "ab AB-+0\t\n\r\x0b\x0c\x1c\x1f_.,lL"
WIDE = "aé€𝄞 "
MAXI = (1 << 63) - 1
fails = 0
cases = 0


def b(s):
    # the Pystachy str of a CPython str: its UTF-8 bytes, one character per byte
    return s.encode("utf-8").decode("latin-1")


def u(s):
    return s.encode("latin-1").decode("utf-8")


def text(alpha=ASCII, n=12):
    if alpha is ASCII and R.randrange(3) == 0:
        alpha = "ab"  # repetitive text: overlapping matches
    return "".join(R.choice(alpha) for _ in range(R.randrange(n + 1)))


def outcome(f, *a):
    try:
        return ("ok", f(*a))
    except Exception as e:  # the runtime raises CPython's exception types and messages
        return (type(e).__name__, str(e))


def ref(f):
    # CPython's outcome, with the text of its result or message as a Pystachy str
    r = outcome(f)
    return (r[0], b(r[1]) if isinstance(r[1], str) else r[1])


def same(name, got, want, args):
    global fails, cases
    cases += 1
    if got != want:
        fails += 1
        if fails <= 20:
            print(f"FAIL {name}{args!r}: runtime.py {got!r}, CPython {want!r}")


def idx():
    return R.choice([0, 1, 2, -1, -3, 5, 40, -40, MAXI, -MAXI - 1])


def fuzz_str():
    for _ in range(N):
        s = text()
        n = text(n=3)
        st, en = idx(), idx()
        for name, mine, ref in [
            ("find", rt.pys_str_find, lambda: s.find(n, st, en)),
            ("rfind", rt.pys_str_rfind, lambda: s.rfind(n, st, en)),
            ("index", rt.pys_str_index, lambda: s.index(n, st, en)),
            ("rindex", rt.pys_str_rindex, lambda: s.rindex(n, st, en)),
            ("count", rt.pys_str_count, lambda: s.count(n, st, en)),
            ("startswith", rt.pys_str_startswith, lambda: int(s.startswith(n, st, en))),
            ("endswith", rt.pys_str_endswith, lambda: int(s.endswith(n, st, en))),
        ]:
            same(name, outcome(mine, s, n, st, en), outcome(ref), (s, n, st, en))
        same("contains", outcome(rt.pys_str_contains, s, n), outcome(lambda: int(n in s)), (s, n))
        r = text(n=3)
        same("replace", outcome(rt.pys_str_replace, s, n, r), outcome(s.replace, n, r), (s, n, r))
        cs = R.choice([None, text(n=3)])
        for name, mine, ref in [("strip", rt.pys_str_strip, s.strip), ("lstrip", rt.pys_str_lstrip, s.lstrip), ("rstrip", rt.pys_str_rstrip, s.rstrip)]:
            same(name, outcome(mine, s, cs), outcome(ref, cs), (s, cs))
        for name in "isdigit isalpha isalnum isspace isupper islower isascii isdecimal isnumeric istitle".split():
            same(name, outcome(getattr(rt, "pys_str_" + name), s), outcome(lambda: int(getattr(s, name)())), (s,))
        for name in "upper lower swapcase capitalize title casefold".split():
            same(name, outcome(getattr(rt, "pys_str_" + name), s), outcome(getattr(s, name)), (s,))
        sep = R.choice([None, None, text(n=2)])
        m = R.choice([-1, -1, 0, 1, 2, 5])
        same("split", outcome(rt.pys_str_split, s, sep, m), outcome(s.split, sep, m), (s, sep, m))
        same("rsplit", outcome(rt.pys_str_rsplit, s, sep, m), outcome(s.rsplit, sep, m), (s, sep, m))
        keep = R.randrange(2)
        same("splitlines", outcome(rt.pys_str_splitlines, s, keep), outcome(s.splitlines, bool(keep)), (s, keep))
        same("partition", outcome(rt.pys_str_partition, s, n), outcome(s.partition, n), (s, n))
        same("rpartition", outcome(rt.pys_str_rpartition, s, n), outcome(s.rpartition, n), (s, n))
        same("removeprefix", outcome(rt.pys_str_removeprefix, s, n), outcome(s.removeprefix, n), (s, n))
        same("removesuffix", outcome(rt.pys_str_removesuffix, s, n), outcome(s.removesuffix, n), (s, n))
        ts = R.choice([-1, 0, 1, 4, 8])
        same("expandtabs", outcome(rt.pys_str_expandtabs, s, ts), outcome(s.expandtabs, ts), (s, ts))
        parts = [text(n=4) for _ in range(R.randrange(4))]
        same("join", outcome(rt.pys_str_join, n, parts), outcome(n.join, parts), (n, parts))
        # widths count characters: compare on UTF-8 text through its bytes
        w = text(WIDE, 6)
        width = R.randrange(-2, 12)
        fill = R.choice([None, R.choice(WIDE), "ab"])
        for name in "ljust rjust center".split():
            ref = outcome(getattr(w, name), width, fill if fill is not None else " ")
            if ref[0] == "ok":
                ref = ("ok", b(ref[1]))
            same(name, outcome(getattr(rt, "pys_str_" + name), b(w), width, b(fill) if fill is not None else None), ref, (w, width, fill))
        z = R.choice(["", "+", "-"]) + text("12é", 4)
        same("zfill", outcome(rt.pys_str_zfill, b(z), width), ("ok", b(z.zfill(width))), (z, width))


def num():
    k = R.randrange(4)
    if k == 0:
        return R.randrange(-30, 31)
    if k == 1:
        return R.randrange(-(1 << 20), 1 << 20)
    return R.randrange(-(1 << 62), 1 << 62)


def fits(r):
    return r[0] != "ok" or -MAXI - 1 <= r[1] <= MAXI


def fuzz_math():
    for _ in range(N):
        a, c = num(), num()
        for name, mine, ref, args in [
            ("gcd", rt.pys_m_gcd, math.gcd, (a, c)),
            ("lcm", rt.pys_m_lcm, math.lcm, (a, c)),
            ("isqrt", rt.pys_m_isqrt, math.isqrt, (a,)),
            ("factorial", rt.pys_m_factorial, math.factorial, (R.randrange(-2, 21),)),
            ("comb", rt.pys_m_comb, math.comb, (R.randrange(-2, 70), R.randrange(-2, 40))),
            ("perm", rt.pys_m_perm, math.perm, (R.randrange(-2, 30), R.randrange(-2, 15))),
        ]:
            want = outcome(ref, *args)
            if fits(want):  # beyond 64 bits the compiled code raises OverflowError (the differential tests check it)
                same(name, outcome(mine, *args), want, args)


M64 = (1 << 64) - 1


def fnv(s):
    # the dict hash of runtime.c before it moved: FNV-1a, then h ^ h >> 29, over unsigned 64 bits
    h = 1469598103934665603
    for c in s.encode("latin-1"):
        h = ((h ^ c) * 1099511628211) & M64
    return h ^ h >> 29


def mix(k):
    h = k & M64
    h = ((h ^ h >> 30) * 0xBF58476D1CE4E5B9) & M64
    return h ^ h >> 31


def fuzz_hash():
    for _ in range(N):
        k = R.choice([num(), R.randrange(-(1 << 63), 1 << 63)])
        same("hash_int", rt.pys_hash_int(k) & M64, mix(k), (k,))
        s = b(text(WIDE + ASCII, 10))
        same("hash_str", rt.pys_hash_str(s) & M64, fnv(s), (s,))


def fmt_float(m, ty, prec, alt):
    # runtime.c's pys_fmt_float (snprintf) writes what CPython's float formatting writes for |x|
    return format(m, ("#" if alt else "") + (f".{prec}" if prec >= 0 else "") + (chr(ty) if ty else ""))


rt.pys_fmt_float = fmt_float


def spec():
    # a random format spec, mostly well-formed
    parts = []
    if R.randrange(3) == 0:
        parts.append(R.choice(["", "*", "0", "é", "€", " "]) + R.choice("<>=^"))
    for opts, k in [("+- ", 4), ("z", 6), ("#", 4), ("0", 4)]:
        if R.randrange(k) == 0:
            parts.append(R.choice(opts))
    if R.randrange(2) == 0:
        parts.append(str(R.choice([0, 1, 5, 12, 30])))
    if R.randrange(5) == 0:
        parts.append(R.choice(",_"))
    if R.randrange(3) == 0:
        parts.append("." + str(R.choice([0, 1, 3, 10, 17])))
    if R.randrange(2) == 0:
        parts.append(R.choice("bcdoxXneEfFgGs%a"))
    elif R.randrange(8) == 0:
        parts.append(R.choice(["\x00", " ", "\t", "é", "𝄞", "\x7f"]))  # types CPython escapes or rejects
    s = "".join(parts)
    if R.randrange(40) == 0:
        s = s + R.choice(["x", "1", ".", ",,", "_,", "a" * 600 + "x", "<\x005"])  # malformed, long, NUL inside
    return s


def fuzz_format():
    for _ in range(N):
        sp = spec()
        v = R.choice([0, 1, -1, 7, -42, 255, 1000000, R.randrange(-(1 << 63), 1 << 63), 0x10FFFF + 1])
        for name, mine, cpy in [
            ("format_int", lambda: rt.pys_format_int(v, 0, b(sp)), lambda: format(v, sp)),
            ("format_bool", lambda: rt.pys_format_int(int(v != 0), 1, b(sp)), lambda: format(v != 0, sp)),
        ]:
            if name == "format_bool" and sp == "":
                continue  # format(True, "") is str(True), decided before pys_format_int
            same(name, outcome(mine), ref(cpy), (v, sp))
        x = R.choice([0.0, -0.0, 1.5, -2.5, 1e16, 1.0e-5, 123456.789, -0.0004, float("inf"), float("nan"), R.uniform(-1e6, 1e6)])
        same("format_float", outcome(rt.pys_format_float, x, b(sp)), ref(lambda: format(x, sp)), (x, sp))
        t = text(WIDE, 6)
        same("format_str", outcome(rt.pys_format_str, b(t), b(sp)), ref(lambda: format(t, sp)), (t, sp))


fuzz_str()
fuzz_math()
fuzz_hash()
fuzz_format()
print(f"{cases} cases, {fails} failed")
sys.exit(1 if fails else 0)
