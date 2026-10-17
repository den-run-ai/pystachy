"""Differential fuzzing of runtime.py on CPython, against CPython's own str methods and math
(and the dict hash functions against the formulas runtime.c used, on unsigned 64-bit ints).

runtime.py is ordinary Python, so CPython runs it, with tools/rt_cpython/_rt.py standing in for
the compiler's primitives: each pys_* function is called directly and compared with what CPython
computes, on random inputs, with no compilation. Strs are ASCII here (where Pystachy behaves exactly
as CPython) plus UTF-8 text for the width methods, which count characters; a Pystachy str is
given as its bytes, one character per byte. 64-bit overflow is not tested here (CPython's ints
grow): the differential tests compile the same code and check it.

The format functions get runtime.c's pys_fmt_float (float digits by snprintf, or by Ryu as repr's
without a type or precision) from CPython's own float formatting, which it reproduces.

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
        ts = R.choice([-1, 0, 1, 4, 8, -2**31, -2**31 - 1, 2**31, 2**62])
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


BYTES = b"ab AB-+0\t\n\r\x0b\x0c\x1c\x85_.,lL\x80\xa0\xc3\xa9\xe2\x82\xac\xed\xa0\xf0\xff"


def bt(s):
    # the Pystachy str of a bytes: a character per byte
    return s.decode("latin-1")


def bref(f):
    # CPython's outcome, its bytes (and those in a list or tuple) as Pystachy strs, a str as the
    # UTF-8 a Pystachy str holds (surrogates too), a bool as an int
    r = outcome(f)
    v = r[1]
    if isinstance(v, bytes):
        v = bt(v)
    elif isinstance(v, (list, tuple)) and all(isinstance(x, bytes) for x in v):
        v = type(v)(bt(x) for x in v)
    elif isinstance(v, str) and r[0] == "ok":
        v = v.encode("utf-8", "surrogatepass").decode("latin-1")
    elif isinstance(v, bool):
        v = int(v)
    return (r[0], v)


def data(n=12):
    alpha = b"ab" if R.randrange(3) == 0 else BYTES
    return bytes(R.choice(alpha) for _ in range(R.randrange(n + 1)))


def fuzz_bytes():
    # runtime.py's bytes operations against CPython's bytes methods and codecs
    for _ in range(N):
        s = data()
        n = data(3)
        st, en = idx(), idx()
        for name in "find rfind index rindex count startswith endswith".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s), bt(n), st, en), bref(lambda: getattr(s, name)(n, st, en)), (s, n, st, en))
        same("bytes.contains", outcome(rt.pys_bytes_contains, bt(s), bt(n)), bref(lambda: n in s), (s, n))
        x = R.choice([0, 97, 255, 256, -1, R.randrange(256)])
        same("bytes.has", outcome(rt.pys_bytes_has, bt(s), x), bref(lambda: x in s), (s, x))
        r = data(3)
        same("bytes.replace", outcome(rt.pys_bytes_replace, bt(s), bt(n), bt(r)), bref(lambda: s.replace(n, r)), (s, n, r))
        k = R.choice([-1, 0, 1, 2])
        same("bytes.replace_count", outcome(rt.pys_bytes_replace_count, bt(s), bt(n), bt(r), k), bref(lambda: s.replace(n, r, k)), (s, n, r, k))
        cs = R.choice([None, data(3)])
        for name in "strip lstrip rstrip".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s), None if cs is None else bt(cs)), bref(lambda: getattr(s, name)(cs)), (s, cs))
        for name in "isdigit isalpha isalnum isspace isupper islower isascii upper lower swapcase capitalize hex".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s)), bref(getattr(s, name)), (s,))
        sep = R.choice([None, None, data(2)])
        m = R.choice([-1, -1, 0, 1, 2, 5])
        same("bytes.split", outcome(rt.pys_bytes_split, bt(s), None if sep is None else bt(sep), m), bref(lambda: s.split(sep, m)), (s, sep, m))
        same("bytes.rsplit", outcome(rt.pys_bytes_rsplit, bt(s), None if sep is None else bt(sep), m), bref(lambda: s.rsplit(sep, m)), (s, sep, m))
        keep = R.randrange(2)
        same("bytes.splitlines", outcome(rt.pys_bytes_splitlines, bt(s), keep), bref(lambda: s.splitlines(bool(keep))), (s, keep))
        for name in "partition rpartition removeprefix removesuffix".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s), bt(n)), bref(lambda: getattr(s, name)(n)), (s, n))
        parts = [data(4) for _ in range(R.randrange(4))]
        same("bytes.join", outcome(rt.pys_bytes_join, bt(n), [bt(p) for p in parts]), bref(lambda: n.join(parts)), (n, parts))
        width = R.randrange(-2, 16)
        fill = R.choice([None, data(1) or b"*", b"ab"])
        for name in "ljust rjust center".split():
            same("bytes." + name, outcome(getattr(rt, "pys_bytes_" + name), bt(s), width, None if fill is None else bt(fill)),
                 bref(lambda: getattr(s, name)(width) if fill is None else getattr(s, name)(width, fill)), (s, width, fill))
        z = R.choice([b"", b"+", b"-"]) + s
        same("bytes.zfill", outcome(rt.pys_bytes_zfill, bt(z), width), bref(lambda: z.zfill(width)), (z, width))
        h = "".join(R.choice("0123456789abcdefABCDEF  \tgx") for _ in range(R.randrange(9)))
        same("bytes.fromhex", outcome(rt.pys_bytes_fromhex, h), bref(lambda: bytes.fromhex(h)), (h,))
        xs = [R.choice([0, 65, 255, 256, -1, R.randrange(256)]) for _ in range(R.randrange(4))]
        same("bytes.from_list", outcome(rt.pys_bytes_from_list, xs), bref(lambda: bytes(xs)), (xs,))
        c = R.choice([-1, 0, 3])
        same("bytes.zeros", outcome(rt.pys_bytes_zeros, c), bref(lambda: bytes(c)), (c,))
        frm = data(4)
        to = bytes(R.choice(BYTES) for _ in range(len(frm) if R.randrange(6) else R.randrange(5)))
        same("bytes.maketrans", outcome(rt.pys_bytes_maketrans, bt(frm), bt(to)), bref(lambda: bytes.maketrans(frm, to)), (frm, to))
        tab = R.choice([None, bytes.maketrans(frm, to) if len(frm) == len(to) else bytes(range(256)),
                        bytes(R.randrange(256) for _ in range(256)), data(3)])
        dl = R.choice([None, b"", data(3)])
        same("bytes.translate", outcome(rt.pys_bytes_translate, bt(s), None if tab is None else bt(tab), None if dl is None else bt(dl)),
             bref(lambda: s.translate(tab) if dl is None else s.translate(tab, dl)), (s, tab, dl))
        hs = R.choice([None, ":", "-", "", "::", "é", "€", b":", b"\xff", b"\x00", b"", b"ab"])
        per = R.choice([1, 2, 3, -1, -2, -3, 0, 7, 2147483647, -2147483648, 2147483648, -2147483649])
        same("bytes.hex_sep", outcome(rt.pys_bytes_hex_sep, bt(s), None if hs is None else bt(hs) if isinstance(hs, bytes) else b(hs),
                                      1 if isinstance(hs, str) else 0, per),
             bref(lambda: s.hex(bytes_per_sep=per) if hs is None else s.hex(hs, per)), (s, hs, per))
        enc = R.choice(["utf-8", "UTF8", "latin-1", "iso-8859-1", "ascii", "us-ascii", "nope"])
        errs = R.choice(["strict", "replace", "ignore", "backslashreplace", "surrogateescape", "surrogatepass", "xmlcharrefreplace", "nope"])
        same("bytes.decode", outcome(rt.pys_bytes_decode, bt(s), enc, errs), bref(lambda: s.decode(enc, errs)), (s, enc, errs))
        t = "".join(R.choice("aé€\U0001d11e \udc80\udcff\ud800") for _ in range(R.randrange(6)))
        same("str.encode", outcome(rt.pys_str_encode, t.encode("utf-8", "surrogatepass").decode("latin-1"), enc, errs), bref(lambda: t.encode(enc, errs)), (t, enc, errs))


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
        q = R.randrange(3037000500 >> R.randrange(32))  # up to the root of 2**63: squares, where the float root can fall short
        for name, mine, ref, args in [
            ("gcd", rt.pys_m_gcd, math.gcd, (a, c)),
            ("lcm", rt.pys_m_lcm, math.lcm, (a, c)),
            ("isqrt", rt.pys_m_isqrt, math.isqrt, (a,)),
            ("isqrt", rt.pys_m_isqrt, math.isqrt, (q * q + R.choice([-1, 0, 1]),)),
            ("factorial", rt.pys_m_factorial, math.factorial, (R.randrange(-2, 21),)),
            ("comb", rt.pys_m_comb, math.comb, (R.randrange(-2, 70), R.randrange(-2, 40))),
            ("perm", rt.pys_m_perm, math.perm, (R.randrange(-2, 30), R.randrange(-2, 15))),
        ]:
            want = outcome(ref, *args)
            if fits(want):  # beyond 64 bits the compiled code raises OverflowError (the differential tests check it)
                same(name, outcome(mine, *args), want, args)
        xs = [real() for _ in range(R.randrange(12))]
        if R.randrange(3) == 0:  # cancellation: the items negated, some halved or one ulp off
            xs += [-x * R.choice([1.0, 0.5, 1.0000000000000002]) for x in xs]
            R.shuffle(xs)
        same("fsum", bits(outcome(rt.pys_m_fsum, xs)), bits(outcome(math.fsum, xs)), (xs,))
        same("prod", bits(outcome(rt.pys_m_prod_float, xs, 1.5)), bits(outcome(lambda: math.prod(xs, start=1.5))), (xs,))
        ns = [R.randrange(-1000, 1001) for _ in range(R.randrange(7))]
        st = R.choice([1, -1, a])
        want = outcome(lambda: math.prod(ns, start=st))
        if fits(want):
            same("prod", outcome(rt.pys_m_prod_int, ns, st), want, (ns, st))


def real():
    # a float for fsum and prod: specials, small ints (exact sums, ties), anything in range
    k = R.randrange(8)
    if k == 0:
        return R.choice([0.0, -0.0, 5e-324, 2.2250738585072014e-308, 1.7976931348623157e308, -1.7976931348623157e308,
                         1e16, 1.0, math.inf, -math.inf, math.nan])
    if k == 1:
        return float(R.randrange(-1000, 1001))
    if k == 2:
        return math.ldexp(R.random() - 0.5, R.randrange(-1074, 1025))
    return (R.random() - 0.5) * 2.0 ** R.randrange(-60, 60)


def bits(r):
    # a float outcome by its bits, so that a nan or a zero's sign compares
    return (r[0], r[1].hex()) if r[0] == "ok" else r


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
    # runtime.c's pys_fmt_float (snprintf, or Ryu) writes what CPython's float formatting writes for |x|
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


def fuzz_search():
    # long needles in repetitive text, where search() gives up its candidate checks for memmem;
    # first a needle right after each number of failed candidates, around the cutover
    for pre in range(40):
        h = "a" * pre + "a" * 10 + "b" + "ab" * 3
        n = "a" * 10 + "b"
        same("find", outcome(rt.pys_str_find, h, n, 0, len(h)), outcome(h.find, n), (h, n))
        same("count", outcome(rt.pys_str_count, h, n, 0, len(h)), outcome(h.count, n), (h, n))
    for _ in range(N // 10):
        unit = "".join(R.choice("ab") for _ in range(R.randrange(1, 4)))
        h = unit * R.randrange(1, 120) + text("ab", 6)
        n = R.choice([h[R.randrange(len(h)) :][: R.randrange(1, 40)], "a" * R.randrange(5, 30) + "b", text("ab", 20)])
        st, en = R.choice([0, 0, 3, -50]), R.choice([len(h), len(h), len(h) - 2, 200])
        for name, mine, ref in [
            ("find", rt.pys_str_find, lambda: h.find(n, st, en)),
            ("rfind", rt.pys_str_rfind, lambda: h.rfind(n, st, en)),
            ("count", rt.pys_str_count, lambda: h.count(n, st, en)),
        ]:
            same(name, outcome(mine, h, n, st, en), outcome(ref), (h, n, st, en))
        same("split", outcome(rt.pys_str_split, h, n, -1), outcome(h.split, n), (h, n))
        same("replace", outcome(rt.pys_str_replace, h, n, "X"), outcome(h.replace, n, "X"), (h, n))
    # HTML-like text: a candidate at each "<", most of them failing, between many occurrences, so
    # count, replace and split go on with memmem once the failures turn out dense
    tags = ["<span>", "</span>", "<b>", "</b>", "<br>", "x", "yz", " "]
    for _ in range(N // 10):
        h = "".join(R.choice(tags) for _ in range(R.randrange(1, 80)))
        n = R.choice(["</span>", "</b>", "<", "</", "span>", "<b>x", "</span><", "<i>"])
        st, en = R.choice([0, 0, 5, -30]), R.choice([len(h), len(h), len(h) - 3, 100])
        for name, mine, ref in [
            ("find", rt.pys_str_find, lambda: h.find(n, st, en)),
            ("count", rt.pys_str_count, lambda: h.count(n, st, en)),
        ]:
            same(name, outcome(mine, h, n, st, en), outcome(ref), (h, n, st, en))
        m = R.choice([-1, -1, 3])
        same("split", outcome(rt.pys_str_split, h, n, m), outcome(h.split, n, m), (h, n, m))
        same("replace", outcome(rt.pys_str_replace, h, n, "X"), outcome(h.replace, n, "X"), (h, n))
    # dense failing candidates first, so memmem takes over at once for a stretch of d bytes
    # (reach()): an occurrence at each place around its end, alone or d bytes after another, at
    # the end of the text or not
    for n in ["</p>", "</span>", "</"]:
        d = rt.reach(0, 0, len(n))  # (so the cases follow its formula)
        for head in ["<x" * 3, "<" * 40]:
            for p in range(d - 40, d + 10):
                for h in [head + "y" * p + n, head + "y" * 5 + n + "y" * p + n + "<y" * 3, head + "y" * p + n + "y" * 9 + n]:
                    same("find", outcome(rt.pys_str_find, h, n, 0, len(h)), outcome(h.find, n), (h, n))
                    same("count", outcome(rt.pys_str_count, h, n, 0, len(h)), outcome(h.count, n), (h, n))
                    same("split", outcome(rt.pys_str_split, h, n, -1), outcome(h.split, n), (h, n))
                    same("replace", outcome(rt.pys_str_replace, h, n, "X"), outcome(h.replace, n, "X"), (h, n))
    # longer text: runs of dense failing candidates and of sparse ones, so memmem's stretches (300
    # bytes and more) end at random places, often around an occurrence, and the candidates are
    # counted again; runs of a byte and single ones, for count's two ways with one byte
    for _ in range(N // 40):
        n = R.choice(["</p>", "</", "<p>x", "</table-of-contents>", "<", "y"])
        parts = []
        for _ in range(R.randrange(1, 6)):
            parts.append(R.choice(["<x", "<p", "<", "</", "y"]) * R.randrange(60))
            parts.append(R.choice(["y", "z", "yz<"]) * R.randrange(400))
            parts.append(R.choice([n, n, n[:-1], "<"]))
        h = "".join(parts)
        st, en = R.choice([0, 0, R.randrange(300)]), R.choice([len(h), len(h), R.randrange(len(h) + 1)])
        for name, mine, ref in [
            ("find", rt.pys_str_find, lambda: h.find(n, st, en)),
            ("count", rt.pys_str_count, lambda: h.count(n, st, en)),
        ]:
            same(name, outcome(mine, h, n, st, en), outcome(ref), (h, n, st, en))
        same("contains", outcome(rt.pys_str_contains, h, n), outcome(lambda: int(n in h)), (h, n))
        m = R.choice([-1, -1, 5])
        same("split", outcome(rt.pys_str_split, h, n, m), outcome(h.split, n, m), (h, n, m))
        same("replace", outcome(rt.pys_str_replace, h, n, "X"), outcome(h.replace, n, "X"), (h, n))


def fuzz_replace():
    # replace past the 65,536 occurrences replaced() lists before it weighs them: dense ones
    # counted and copied as they are found, sparse ones listed on, and texts that change between
    # the two, with a count that stops before, at or after each place the way changes
    def check(h, n, r, k):
        h, n, r = b(h), b(n), b(r)
        same("replace", outcome(rt.pys_str_replace_count, h, n, r, k), outcome(h.replace, n, r, k), (len(h), n, r, k))

    cap = 65536
    for g in [0, 1, 15, 16, 17]:  # an occurrence every g + 1 bytes: dense up to 16
        for i, k in enumerate([-1, cap - 1, cap, cap + 1, 2 * cap + 3]):
            check(("*" + "y" * g) * (cap + 40) + "end", "*", ["", "_", ";;", "é", "XYZ"][(i + g) % 5], k)
    check("*" * cap, "*", "_", -1)  # exactly the listed ones, none left to count
    check("*" * (cap + 2), "*", "_", cap + 1)  # one more left than count lets go
    for n, unit in [("ab", "aba"), ("</p>", "</p><"), ("aab", "aaab")]:  # failed candidates
        for k in [-1, cap + 5]:
            check(unit * (cap + 40), n, "_", k)
    check("a," * (cap + 7), ",", ";", -1)
    # dense, but failed candidates costlier than the bytes they pass, so the rest is listed (DNA's
    # "CA" in ACG, and a run of the needle's first byte after a dense prefix), and cheap ones
    for k, n in [(3, "CA"), (4, "GA"), (2, "CAC")]:
        dna = "".join(R.choice("ACGT"[:k]) for _ in range(1100000))
        for c in [-1, cap + 1, R.randrange(cap, dna.count(n) + 2)]:
            check(dna, n, R.choice(["", "#", "<n>"]), c)
    for n in ["ab", "a" * 15 + "b", "é" * 3 + "è"]:
        for c in [-1, cap + 1, 70000, 70001]:
            check(n * 70000 + n[0] * 30000 + n, n, "_", c)
    for n, unit in [("aa", "a"), ("aaa", "a"), ("abab", "ab")]:  # needles that overlap themselves
        for c in [-1, cap + 1]:
            check(unit * (3 * cap * len(n) + 7), n, "-", c)
    for c in [-1, cap + 1, 140000]:
        check("ab" * 70000 + ("a" * 40 + "ab") * 300 + "ab" * 100000, "ab", "Z", c)
        check(("ab" + "y" * 13 + "ab" + "y" * 12 + "a") * 40000, "ab", "", c)
    for n, r in [("ab", "X"), ("é", ""), ("</p>", "\n"), ("aa", "b"), ("𝄞", "→")]:
        for k in [-1, cap + 1]:
            check((n + "y") * (cap + 40) + n[:-1], n, r, k)
    for _ in range(max(2, N // 2500)):
        n = R.choice(["*", ",", "ab", "\r\n", "é", "𝄞", "</p>", "aa"])
        r = R.choice(["", "_", ";;", "XYZ", "é", "\n", n])
        parts = []
        while len(parts) < 3 or R.randrange(3):
            gap = R.choice(["", "y", "é", "yz" * R.randrange(8), "y" * R.randrange(17, 80), "a", "a" * R.randrange(40)])
            parts.append((n + gap) * R.randrange(1, 70000))
        h = "".join(parts)
        k = R.choice([-1, -1, cap - 1, cap, cap + 1, 3 * cap, R.randrange(h.count(n) + 2)])
        check(h, n, r, k)


fuzz_str()
fuzz_replace()
fuzz_bytes()
fuzz_search()
fuzz_math()
fuzz_hash()
fuzz_format()
print(f"{cases} cases, {fails} failed")
sys.exit(1 if fails else 0)
