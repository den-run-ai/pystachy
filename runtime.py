"""Pystachy runtime, the part written in the subset itself.

`pystachy rt runtime.py` compiles it like a program, but each `pys_*` function is defined under
its C name with runtime.c's types (bools cross as int), and the driver links it to runtime.c's
bitcode into the cached runtime (build/runtime-py-<L>-<K>.bc and its .o, named by a hash of
what they are built from, this file's bytes among it). runtime.c keeps a
prototype of each function moved here. Programs call these functions exactly as they call
runtime.c's, so their IR does not change (but for an invoke inside a try, where RUNTIME says a
function moved here can raise and runtime.c's could not).

The rules for this file: functions, imports and docstrings only (nothing runs module code); no
classes; no bools in a pys_* signature; and a function may not use the operation it implements
(math.gcd() inside pys_m_gcd would call itself). CPython can run it too, where its strs hold
bytes (as pystachy.py reads source files, as Latin-1).
"""
import math

import _rt


# ---------- the math module's integer functions ----------
# The subset's arithmetic is checked, so an int result that does not fit in 64 bits raises
# CPython's OverflowError where runtime.c had to test for it by hand. There are no unsigned or
# 128-bit ints: gcd divides unsigned 64-bit patterns with _rt.urem (|-2**63| fits in them), and
# comb asks _rt.mul_ovf before it multiplies.


def pys_m_gcd(a: int, b: int) -> int:
    x = _rt.wrap_sub(0, a) if a < 0 else a  # |a| as an unsigned 64-bit pattern
    y = _rt.wrap_sub(0, b) if b < 0 else b
    while y != 0:
        t = _rt.urem(x, y)
        x = y
        y = t
    if x < 0:
        raise OverflowError("integer result does not fit in 64 bits")  # gcd(-2**63, 0) = 2**63
    return x


def pys_m_lcm(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    r = a // pys_m_gcd(a, b) * b
    return -r if r < 0 else r


def pys_m_isqrt(n: int) -> int:
    if n < 0:
        raise ValueError("isqrt() argument must be nonnegative")
    # the float root is within one of the answer; squares fix it up, which cost less than quotients
    # (mul_ovf: a square past the largest int is past n)
    r = int(math.sqrt(float(n)))
    while _rt.mul_ovf(r, r) or r * r > n:
        r -= 1
    while not _rt.mul_ovf(r + 1, r + 1) and (r + 1) * (r + 1) <= n:
        r += 1
    return r


def pys_m_factorial(n: int) -> int:
    if n < 0:
        raise ValueError("factorial() not defined for negative values")
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


def nonneg(n: int, k: int) -> None:
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    if k < 0:
        raise ValueError("k must be a non-negative integer")


def pys_m_comb(n: int, k: int) -> int:
    nonneg(n, k)
    if k > n:
        return 0
    if k > n - k:
        k = n - k
    # r = C(n - k + i, i) after step i, which never exceeds the result. i divides r * m, so where
    # that product overflows, r * m // i is r // i * m + r % i * m // i, and no step overflows
    # unless the result does (r % i * m < i * m, and where i * m reaches 2**63 so does C(n, k)).
    # All are positive: unsigned division, which is much faster than floor division
    r = 1
    for i in range(1, k + 1):
        m = n - k + i
        if _rt.mul_ovf(r, m):
            r = _rt.udiv(r, i) * m + _rt.udiv(_rt.urem(r, i) * m, i)
        else:
            r = _rt.udiv(r * m, i)
    return r


def pys_m_perm(n: int, k: int) -> int:
    nonneg(n, k)
    if k > n:
        return 0
    r = 1
    for i in range(k):
        r *= n - i
    return r


# ---------- math.fsum and math.prod ----------
# fsum is CPython's math_fsum, Shewchuk's exact summation: the partials hold the sum so far
# exactly, as nonzero, nonoverlapping floats increasing in magnitude, and are rounded once at the
# end; infs and nans are summed apart. prod multiplies left to right, ints with the checked
# arithmetic. Where CPython makes a float of an int item (in fsum, and in a product with a
# float), the compiler passes the list through pys_m_floats.


def pys_m_fsum(xs: list[float]) -> float:
    p: list[float] = []  # the partials: p[:n]
    n = 0
    special = 0.0  # the sum of the infs and nans
    infs = 0.0  # of the infs: a nan if both signs occur
    for v in xs:
        x = v
        i = 0
        for j in range(n):
            y = p[j]
            if abs(x) < abs(y):
                t = x
                x = y
                y = t
            hi = x + y
            lo = y - (hi - x)
            if lo != 0.0:
                p[i] = lo
                i += 1
            x = hi
        n = i
        if x != 0.0:
            if not math.isfinite(x):
                # an inf or a nan, or a sum past the largest float
                if math.isfinite(v):
                    raise OverflowError("intermediate overflow in fsum")
                if math.isinf(v):
                    infs += v
                special += v
                n = 0
            else:
                if n == len(p):
                    p.append(x)
                else:
                    p[n] = x
                n += 1
    if special != 0.0:
        if math.isnan(infs):
            raise ValueError("-inf + inf in fsum")
        return special
    hi = 0.0
    lo = 0.0
    if n > 0:
        # the partials from the largest down, while their sum is exact
        n -= 1
        hi = p[n]
        while n > 0:
            x = hi
            n -= 1
            y = p[n]
            hi = x + y
            lo = y - (hi - x)
            if lo != 0.0:
                break
        # half-even rounding across the partials: the rest of them may break a tie
        if n > 0 and ((lo < 0.0 and p[n - 1] < 0.0) or (lo > 0.0 and p[n - 1] > 0.0)):
            y = lo * 2.0
            x = hi + y
            if y == x - hi:
                hi = x
    return hi


def pys_m_prod_int(xs: list[int], start: int) -> int:
    r = start
    for x in xs:
        r *= x
    return r


def pys_m_prod_float(xs: list[float], start: float) -> float:
    r = start
    for x in xs:
        r *= x
    return r


def pys_m_floats(xs: list[int]) -> list[float]:
    return [float(x) for x in xs]


# ---------- str methods ----------
# A str is a length and its bytes (UTF-8). _rt.byte reads one without making a 1-char str, and
# _rt.str_new/str_put/copy/str_done build a new str in place, where runtime.c used memcpy, memmem
# and its Buf. Case mapping, the is*() tests and whitespace know only ASCII, as in runtime.c.


def adj_start(st: int, n: int) -> int:
    # CPython's ADJUST_INDICES, for s[st:en] in the search methods (adj_end: the end)
    if st < 0:
        st += n
        if st < 0:
            st = 0
    return st


def adj_end(en: int, n: int) -> int:
    if en > n:
        return n
    if en < 0:
        en += n
        if en < 0:
            en = 0
    return en


def match(h: str, i: int, n: str) -> bool:
    # whether n occurs in h at i, which leaves room for it, given that its first byte does: byte by
    # byte while it is short, else memcmp. (A wrapping add, as byte() checks the index anyway: match
    # and scan stay small enough for LLVM to inline into both search loops.)
    m = len(n)
    if m > 8:
        return _rt.same(h, i, n, 0, m)
    for j in range(1, m):
        if _rt.byte(h, _rt.wrap_add(i, j)) != _rt.byte(n, j):
            return False
    return True


def scan(s: str, c: int, i: int, n: int) -> int:
    # the first k in [i, n) where byte k of s is c, or -1: inline over 8 bytes (dense candidates),
    # then memchr (sparse ones). (Scans are range loops, which step with an nsw add where a while
    # loop's += is checked; byte()'s index check stays, as LLVM cannot tell that n <= len(s).)
    stop = _rt.wrap_add(i, 8)
    if stop > n:
        stop = n
    for k in range(i, stop):
        if _rt.byte(s, k) == c:
            return k
    return _rt.find_byte(s, c, stop, n) if stop < n else -1


def scan_ws(s: str, i: int, n: int, want: bool) -> int:
    # the first k in [i, n) where the character at k is whitespace (want) or not, or n. (The
    # index steps by a character's 1 to 4 bytes within s: wrapping adds, which cannot overflow,
    # here and in the other character loops below. Each loop tests an ASCII byte itself, and
    # calls wsat() and its kin, which LLVM does not inline, only for a non-ASCII one, as
    # runtime.c's ws() calls uws())
    k = i
    while k < n:
        c = _rt.byte(s, k)
        w = (1 if ws(c) else -1) if c < 128 else wsat(s, k, n)
        if (w > 0) == want:
            return k
        k = _rt.wrap_add(k, w) if w > 0 else _rt.wrap_sub(k, w)
    return n


def search(h: str, n: str, st: int, en: int) -> int:
    # the first i from st on where n occurs in h[:en], or -1. One byte goes to memchr, as runtime.c's
    # memmem sent it, not to seek()'s inline scan, whose exit mispredicts where the gaps between hits
    # vary (a loop of finds over the fields of CSV lines, lines, tags). (Here, not in seek(), which
    # in and count call for every search: a test there costs a short in 8% under the JIT)
    if len(n) == 1:
        return _rt.find_byte(h, _rt.byte(n, 0), st, en) if st < en else -1
    i = seek(h, n, st, en, st)
    return -2 - i if i < -1 else i


def seek(h: str, n: str, i: int, en: int, st: int) -> int:
    # search() from i, but -2 - k where memmem found k, in a loop over the occurrences that began
    # at st (again()). The next occurrence of n's first byte (scan), checked. A failed candidate
    # costs toll(len(n)) bytes of memmem's work; once failed candidates have cost more than the
    # bytes passed (and 64), memmem takes over for a stretch (stretch()), which is linear: the work
    # stays below about twice the text's length (Go's strings.Index makes a similar cutover). A
    # first byte as common as each "<" of HTML for "</span>" thus goes to memmem soon, as runtime.c
    # did, and a rare one stays with memchr, which is much faster there
    m = len(n)
    if m == 0:
        return i if i <= en else -1
    first = _rt.byte(n, 0)
    last = en - m  # the last place n can start
    paid = i - 64  # where the failed candidates' cost has reached: once past one, memmem
    while i <= last:
        k = scan(h, first, i, last + 1)
        if k < 0 or match(h, k, n):
            return k
        paid += toll(m)
        i = k + 1
        if paid > k:
            i = stretch(h, n, i, en, st)
            if i < 0:
                return i
            paid = i - 64
    return -1


def toll(m: int) -> int:
    # the cost of a failed candidate for a needle of m bytes, in bytes of memmem's work: memmem
    # skips about m - 1 bytes a step, and a candidate's scan, call and check cost about as much as
    # its steps over 12 times that where candidates are evenly spaced; at the irregular distances
    # of real text they mispredict, and 20 times that keeps the most text near memmem's time (a
    # sweep over real HTML and prose, docs/runtime-in-subset.md 2.10). It covers the up to m
    # comparisons too. (Wrapping, as m is a str's length, far below 2**59: LLVM computes toll()
    # and reach() at the start of every search, where overflow tests would cost each call.)
    return _rt.wrap_mul(_rt.wrap_sub(m, 1), 20)


def reach(i: int, st: int, m: int) -> int:
    # where a stretch of memmem from i ends, for a needle of m bytes: as far again as from st, but
    # at least 16 * m + 256 bytes on, as each stretch costs memmem a setup and seek() a candidate,
    # which can take m bytes each
    d = _rt.wrap_add(_rt.wrap_mul(m, 16), 256)
    return i + (i - st if i - st > d else d)


def stretch(h: str, n: str, i: int, en: int, st: int) -> int:
    # memmem from i to reach(): -2 - k where it found k, else -1 at the end, or where seek() counts
    # the candidates again. A loop over the occurrences goes on from each one memmem found, so a
    # dense text sees few such restarts, and a few tags before long paragraphs do not keep the
    # paragraphs from memchr
    m = len(n)
    stop = reach(i, st, m)
    if stop > en - m:
        k = _rt.find_sub(h, n, i, en)
        return -2 - k if k >= 0 else -1
    k = _rt.find_sub(h, n, i, stop + m - 1)
    return -2 - k if k >= 0 else stop


def again(h: str, n: str, i: int, en: int, st: int, dense: bool) -> int:
    # the next seek() of a loop over the occurrences of n that began at st: a stretch of memmem
    # first where memmem found the last one (dense)
    if dense:
        i = stretch(h, n, i, en, st)
        if i < 0:
            return i
    return seek(h, n, i, en, st)


def rsearch(h: str, n: str, st: int, en: int) -> int:
    # the last i from st on where n occurs in h[:en], or -1: runtime.c's loop, right to left,
    # with memcmp, which LLVM expands where the needle is a constant
    m = len(n)
    for k in range(en - m, st - 1, -1):
        if _rt.same(h, k, n, 0, m):
            return k
    return -1


def pys_str_find(h: str, n: str, st: int, en: int) -> int:
    st = adj_start(st, len(h))
    en = adj_end(en, len(h))
    if en - st < len(n):
        return -1
    return search(h, n, st, en)


def pys_str_rfind(h: str, n: str, st: int, en: int) -> int:
    return rsearch(h, n, adj_start(st, len(h)), adj_end(en, len(h)))


def pys_str_index(h: str, n: str, st: int, en: int) -> int:
    i = pys_str_find(h, n, st, en)
    if i < 0:
        raise ValueError("substring not found")
    return i


def pys_str_rindex(h: str, n: str, st: int, en: int) -> int:
    i = pys_str_rfind(h, n, st, en)
    if i < 0:
        raise ValueError("substring not found")
    return i


def pys_str_count(h: str, n: str, st: int, en: int) -> int:
    st = adj_start(st, len(h))
    en = adj_end(en, len(h))
    m = len(n)
    if en - st < m:
        return 0
    if m == 0:
        return en - st + 1
    first = _rt.byte(n, 0)
    c = 0
    if m == 1:
        # memchr from each occurrence to the next, 16 occurrences at a time, but an inline scan
        # (scan()) for the next 16 where those came within 4 bytes of each other on average: a call
        # for each is slow where they are that dense, and an inline scan mispredicts its exit at
        # each "<" of HTML
        k = _rt.find_byte(h, first, st, en)
        dense = False
        while k >= 0:
            j = k
            t = c + 16
            if dense:
                while k >= 0 and c < t:
                    c += 1
                    k = scan(h, first, k + 1, en)
            else:
                while k >= 0 and c < t:
                    c += 1
                    k = _rt.find_byte(h, first, k + 1, en)
            dense = k - j < 64
        return c
    # seek()'s loop, counting, without a call per occurrence
    last = en - m
    i = st
    while i <= last:
        paid = i - 64
        while True:
            if i > last:
                return c
            k = scan(h, first, i, last + 1)
            if k < 0:
                return c
            if match(h, k, n):
                c += 1
                i = k + m
            else:
                paid += toll(m)
                i = k + 1
                if paid > k:
                    break
        # stretch()'s memmem, from each occurrence it finds, then the candidates again
        while True:
            stop = reach(i, st, m)
            k = _rt.find_sub(h, n, i, en if stop > last else stop + m - 1)
            if k < 0:
                break
            c += 1
            i = k + m
        if stop > last:
            return c
        i = stop
    return c


def pys_str_contains(h: str, n: str) -> int:
    return 1 if len(n) <= len(h) and seek(h, n, 0, len(h), 0) != -1 else 0


def tail(s: str, p: str, st: int, en: int, end: bool) -> int:
    # CPython's tailmatch: s[st:en] starts (or ends) with p
    st = adj_start(st, len(s))
    en = adj_end(en, len(s))
    if en - len(p) < st:
        return 0
    return 1 if _rt.same(s, en - len(p) if end else st, p, 0, len(p)) else 0


def pys_str_startswith(s: str, p: str, st: int, en: int) -> int:
    return tail(s, p, st, en, False)


def pys_str_endswith(s: str, p: str, st: int, en: int) -> int:
    return tail(s, p, st, en, True)


def pys_str_replace(s: str, a: str, b: str) -> str:
    return replaced(s, a, b, -1)


def pys_str_replace_count(s: str, a: str, b: str, count: int) -> str:
    return replaced(s, a, b, count)


def tally(h: str, n: str, st: int, most: int) -> int:
    # pys_str_count(h, n, st, len(h)), up to most. One-byte needles use its optimized counting
    # loop in bounded chunks, so a small count does not search a long unchanged tail and a large
    # count keeps the same throughput. Multi-byte needles are counted by seek()'s
    # candidates; but -1 once the failed ones have cost more than the bytes passed (and 64), where
    # the count would go to memmem. replaced() then lists on: a text of costly candidates is
    # searched once, as before, not counted and searched again (DNA's "CA" in ACG took 1.6 times
    # as long, and "ab" * 70000 + "a" * 20000000 + "ab" 1.3 times)
    m = len(n)
    if m == 1:
        c = 0
        while st < len(h) and c < most:
            end = st + min(len(h) - st, max(65536, most - c))
            c += pys_str_count(h, n, st, end)
            st = end
        return min(c, most)
    first = _rt.byte(n, 0)
    last = len(h) - m
    c = 0
    i = st
    paid = st - 64
    while i <= last:
        k = scan(h, first, i, last + 1)
        if k < 0:
            break
        if match(h, k, n):
            c += 1
            if c == most:
                break
            i = k + m
        else:
            paid += toll(m)
            if paid > k:
                return -1
            i = k + 1
    return c


def replaced(s: str, a: str, b: str, count: int) -> str:
    # the first count occurrences of a replaced (all of them for a negative count), as CPython's
    # replace() makes them
    n = len(s)
    if count == 0:
        return s
    if count < 0 or count > n:
        count = n + 1  # (more than a can occur)
    if len(a) == 0:
        # b before each of the first count - 1 bytes, and then once more (at the end, if count
        # reaches it)
        r = _rt.str_new(n + count * len(b))
        at = 0
        for i in range(count - 1):
            _rt.copy(r, at, b, 0, len(b))
            _rt.str_put(r, at + len(b), _rt.byte(s, i))
            at += len(b) + 1
        _rt.copy(r, at, b, 0, len(b))
        _rt.copy(r, at + len(b), s, count - 1, n - count + 1)
        return _rt.str_done(r)
    pos: list[int] = []  # where a occurs: one search pass, not one to count and one to copy
    dense = False
    j = 0
    cap = 65536  # occurrences listed before the list is weighed against the text it covers
    weigh = 16  # bytes per occurrence at most for replaced_dense(): 0 once tally() gives up
    while True:
        stop = count if count < cap else cap  # (the inner loop as before: its test the only one)
        while len(pos) < stop:
            j = again(s, a, j, n, 0, dense)
            if j == -1:
                break
            dense = j < -1
            if dense:
                j = -2 - j
            pos.append(j)
            j += len(a)
        if j == -1 or len(pos) == count:
            break
        if j <= cap * weigh:
            # A bounded count must stop counting at its limit, including for one-byte needles.
            rest = pys_str_count(s, a, j, n) if len(a) == 1 and count >= n else tally(s, a, j, count - len(pos))
            if rest >= 0:
                return replaced_dense(s, a, b, count, pos, rest)
            weigh = 0  # costly candidates (DNA's "CA" in ACG): searched once, listed
        cap *= 2  # sparse (long separators, lines): one pass, listed
    r = _rt.str_new(n + len(pos) * (len(b) - len(a)))
    i = 0
    at = 0
    for j in pos:
        _rt.copy(r, at, s, i, j - i)
        _rt.copy(r, at + j - i, b, 0, len(b))
        at += j - i + len(b)
        i = j + len(a)
    _rt.copy(r, at, s, i, n - i)
    return _rt.str_done(r)


def replaced_dense(s: str, a: str, b: str, count: int, pos: list[int], rest: int) -> str:
    # replaced() where its list pos of the first occurrences shows one every 16 bytes or more
    # often, so that a list of them all would outgrow the result ("*" * 10**7 replaced by "" took
    # 7.6 times runtime.c's memory), and rest more were counted after them: the result allocated
    # at its final size and each further occurrence copied into it as it is found, as runtime.c's
    # replace did. An empty gap or replacement costs no copy, and one byte of replacement a store.
    # The search is scan() and match(), not again(), whose seek() LLVM inlines into replaced()
    # only while that is its one caller: tally() found the failed candidates no costlier than
    # the bytes they passed, so these are the same candidates at the same cost
    n = len(s)
    m = len(a)
    lb = len(b)
    c = _rt.byte(b, 0) if lb == 1 else 0
    first = _rt.byte(a, 0)
    if rest > count - len(pos):
        rest = count - len(pos)
    r = _rt.str_new(n + (len(pos) + rest) * (lb - m))
    i = 0
    at = 0
    for t in range(len(pos) + rest):
        if t < len(pos):
            j = pos[t]
        else:
            j = scan(s, first, i, n - m + 1)
            while not match(s, j, a):
                j = scan(s, first, j + 1, n - m + 1)
        if j > i:
            _rt.copy(r, at, s, i, j - i)
            at += j - i
        if lb == 1:
            _rt.str_put(r, at, c)
        elif lb > 1:
            _rt.copy(r, at, b, 0, lb)
        at += lb
        i = j + m
    _rt.copy(r, at, s, i, n - i)
    return _rt.str_done(r)


def ws(c: int) -> bool:
    # an ASCII whitespace byte
    return c == 32 or (c >= 9 and c <= 13) or (c >= 28 and c <= 31)


def uchar(s: str, i: int, n: int) -> int:
    # the character at byte i of s[:n] (i < n), as runtime.c's u8char reads it: a UTF-8 sequence
    # as chr() writes it (no overlong form, nothing above U+10FFFF), else the one byte. Its code
    # point * 8 + its byte count
    c = _rt.byte(s, i)
    k = 1 if c > 244 else 4 if c >= 240 else 3 if c >= 224 else 2 if c >= 194 else 1
    if k == 1 or k > _rt.wrap_sub(n, i):
        return c * 8 + 1
    v = c & (127 >> k)
    for j in range(1, k):
        b = _rt.byte(s, _rt.wrap_add(i, j))
        if b & 192 != 128:
            return c * 8 + 1
        v = _rt.shl(v, 6) | (b & 63)  # (below 2**21)
    if v < (128 if k == 2 else 2048 if k == 3 else 65536) or v > 1114111:
        return c * 8 + 1
    return _rt.shl(v, 3) | k


def uspace(cp: int) -> bool:
    # str.isspace() of code point cp (Unicode 15.1, CPython 3.13): ASCII's and these
    if cp < 128:
        return ws(cp)
    return cp == 133 or cp == 160 or cp == 5760 or (cp >= 8192 and cp <= 8202) or cp == 8232 or cp == 8233 or cp == 8239 or cp == 8287 or cp == 12288


def wsat(s: str, i: int, n: int) -> int:
    # the character at byte i of s[:n] is whitespace: its byte count, else minus that (an ASCII
    # byte is tested inline; only a non-ASCII one is decoded)
    c = _rt.byte(s, i)
    if c < 128:
        return 1 if ws(c) else -1
    u = uchar(s, i, n)
    return u & 7 if uspace(u >> 3) else -(u & 7)


def back(s: str, j: int) -> int:
    # the byte count of the character that ends at byte j (j > 0): a UTF-8 sequence that ends
    # there, as uchar reads it, else one byte (runtime.c's uback)
    if _rt.byte(s, _rt.wrap_sub(j, 1)) < 128:
        return 1
    i = _rt.wrap_sub(j, 1)
    while i > 0 and _rt.wrap_sub(j, i) < 4 and _rt.byte(s, i) & 192 == 128:
        i = _rt.wrap_sub(i, 1)
    return _rt.wrap_sub(j, i) if uchar(s, i, j) & 7 == _rt.wrap_sub(j, i) else 1


def wsback(s: str, j: int) -> int:
    # as wsat, for the character that ends at byte j (j > 0)
    c = _rt.byte(s, _rt.wrap_sub(j, 1))
    if c < 128:
        return 1 if ws(c) else -1
    b = back(s, j)
    return wsat(s, _rt.wrap_sub(j, b), j)


def stripped(s: str, i: int, n: int, cs: str) -> int:
    # as wsat, for the characters of cs (whitespace if cs was omitted: null), so that a
    # character of several bytes is stripped whole or not at all, as CPython strips code points
    if _rt.null(cs):
        return wsat(s, i, n)
    c = _rt.byte(s, i)
    if c < 128:
        return 1 if _rt.find_byte(cs, c, 0, len(cs)) >= 0 else -1
    k = uchar(s, i, n) & 7
    j = 0
    while j < len(cs):
        m = uchar(cs, j, len(cs)) & 7
        if m == k and _rt.same(cs, j, s, i, m):
            return k
        j = _rt.wrap_add(j, m)
    return -k


def strip_byte(c: int, cs: str) -> bool:
    # whether strip() strips the ASCII byte c: whitespace if cs was omitted (null), else a byte of cs
    return ws(c) if _rt.null(cs) else _rt.find_byte(cs, c, 0, len(cs)) >= 0


def strip(s: str, cs: str, m: int) -> str:
    # m: 1 left, 2 right, 3 both; character by character (an ASCII byte tested here, see scan_ws)
    i = 0
    j = len(s)
    if m & 1:
        while i < j:
            c = _rt.byte(s, i)
            k = (1 if strip_byte(c, cs) else -1) if c < 128 else stripped(s, i, j, cs)
            if k < 0:
                break
            i = _rt.wrap_add(i, k)
    if m & 2:
        while j > i:
            c = _rt.byte(s, _rt.wrap_sub(j, 1))
            if c < 128:
                if not strip_byte(c, cs):
                    break
                j = _rt.wrap_sub(j, 1)
            else:
                b = back(s, j)
                if stripped(s, _rt.wrap_sub(j, b), j, cs) < 0:
                    break
                j = _rt.wrap_sub(j, b)
    return s[i:j]


def pys_str_strip(s: str, cs: str) -> str:
    return strip(s, cs, 3)


def pys_str_lstrip(s: str, cs: str) -> str:
    return strip(s, cs, 1)


def pys_str_rstrip(s: str, cs: str) -> str:
    return strip(s, cs, 2)


def digit(c: int) -> bool:
    return c >= 48 and c <= 57


def lowc(c: int) -> bool:
    return c >= 97 and c <= 122


def upc(c: int) -> bool:
    return c >= 65 and c <= 90


def every(s: str, k: int) -> int:
    # all bytes are: 0 digits, 1 letters, 2 either; and there is one
    if len(s) == 0:
        return 0
    for i in range(len(s)):
        c = _rt.byte(s, i)
        d = digit(c)
        a = lowc(c | 32)
        if not (d if k == 0 else a if k == 1 else d or a):
            return 0
    return 1


def cased(s: str, up: bool) -> int:
    # isupper / islower
    seen = 0
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if lowc(c):
            if up:
                return 0
            seen = 1
        if upc(c):
            if not up:
                return 0
            seen = 1
    return seen


def pys_str_isdigit(s: str) -> int:
    return every(s, 0)


def pys_str_isalpha(s: str) -> int:
    return every(s, 1)


def pys_str_isalnum(s: str) -> int:
    return every(s, 2)


def pys_str_isspace(s: str) -> int:
    # all characters are whitespace (Unicode's, character by character), and there is one
    return 1 if len(s) > 0 and scan_ws(s, 0, len(s), False) == len(s) else 0


def pys_str_isupper(s: str) -> int:
    return cased(s, True)


def pys_str_islower(s: str) -> int:
    return cased(s, False)


def pys_str_isdecimal(s: str) -> int:
    return every(s, 0)


def pys_str_isnumeric(s: str) -> int:
    return every(s, 0)


def pys_str_isascii(s: str) -> int:
    for i in range(len(s)):
        if _rt.byte(s, i) > 127:
            return 0
    return 1


def mapcase(s: str, how: int) -> str:
    # 0 lower, 1 upper, 2 swap: ASCII letters only (one loop per case, which LLVM vectorizes)
    n = len(s)
    r = _rt.str_new(n)
    if how == 0:
        for i in range(n):
            c = _rt.byte(s, i)
            _rt.str_put(r, i, c | 32 if upc(c) else c)
    elif how == 1:
        for i in range(n):
            c = _rt.byte(s, i)
            _rt.str_put(r, i, c & 223 if lowc(c) else c)
    else:
        for i in range(n):
            c = _rt.byte(s, i)
            _rt.str_put(r, i, c ^ 32 if lowc(c | 32) else c)  # a letter of either case: one range test
    return _rt.str_done(r)


def pys_str_upper(s: str) -> str:
    return mapcase(s, 1)


def pys_str_lower(s: str) -> str:
    return mapcase(s, 0)


def pys_str_casefold(s: str) -> str:
    return mapcase(s, 0)


def pys_str_swapcase(s: str) -> str:
    return mapcase(s, 2)


def pys_str_capitalize(s: str) -> str:
    r = _rt.str_new(len(s))
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if (i == 0 and lowc(c)) or (i > 0 and upc(c)):
            c ^= 32
        _rt.str_put(r, i, c)
    return _rt.str_done(r)


def pys_str_title(s: str) -> str:
    # a letter after a letter is lowered, any other raised
    r = _rt.str_new(len(s))
    prev = False
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if (prev and upc(c)) or (not prev and lowc(c)):
            _rt.str_put(r, i, c ^ 32)
        else:
            _rt.str_put(r, i, c)
        prev = lowc(c) or upc(c)
    return _rt.str_done(r)


def pys_str_istitle(s: str) -> int:
    # CPython's istitle, over ASCII letters
    prev = False
    seen = 0
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if upc(c):
            if prev:
                return 0
            prev = True
            seen = 1
        elif lowc(c):
            if not prev:
                return 0
            prev = True
            seen = 1
        else:
            prev = False
    return seen


def ulen(s: str) -> int:
    # the length in characters: the bytes that do not continue a UTF-8 sequence
    k = 0
    for i in range(len(s)):
        if _rt.byte(s, i) & 192 != 128:
            k += 1
    return k


def fillrun(r: str, at: int, fill: str, count: int) -> None:
    # count copies of fill into r from byte at: one copy, then copies of what is there, doubling
    total = count * len(fill)
    if total <= 0:
        return
    _rt.copy(r, at, fill, 0, len(fill))
    done = len(fill)
    while done < total:
        k = done if done <= total - done else total - done
        _rt.copy(r, at + done, r, at, k)
        done += k


def pad(s: str, w: int, fill: str, how: int) -> str:
    # how: 0 right, 1 left, 2 center; widths count characters; fill is null for a space
    if not _rt.null(fill) and ulen(fill) != 1:
        raise TypeError("The fill character must be exactly one character long")
    f = " " if _rt.null(fill) else fill
    n = ulen(s)
    if n >= w:
        return s
    gap = w - n
    left = 0 if how == 1 else gap if how == 0 else gap // 2 + (gap & w & 1)  # CPython's centering
    if len(f) == 1:
        # one byte: stores that LLVM turns into memset, and calls small enough to inline
        if gap > 9223372036854775807 - len(s):
            raise MemoryError
        c = _rt.byte(f, 0)
        r = _rt.str_new(len(s) + gap)
        for i in range(left):
            _rt.str_put(r, i, c)
        _rt.copy(r, left, s, 0, len(s))
        for i in range(left + len(s), len(s) + gap):
            _rt.str_put(r, i, c)
        return _rt.str_done(r)
    if gap > (9223372036854775807 - len(s)) // len(f):
        raise MemoryError
    r = _rt.str_new(len(s) + gap * len(f))
    fillrun(r, 0, f, left)
    _rt.copy(r, left * len(f), s, 0, len(s))
    fillrun(r, left * len(f) + len(s), f, gap - left)
    return _rt.str_done(r)


def pys_str_ljust(s: str, w: int, fill: str) -> str:
    return pad(s, w, fill, 1)


def pys_str_rjust(s: str, w: int, fill: str) -> str:
    return pad(s, w, fill, 0)


def pys_str_center(s: str, w: int, fill: str) -> str:
    return pad(s, w, fill, 2)


def pys_str_zfill(s: str, w: int) -> str:
    n = ulen(s)
    if n >= w:
        return s
    z = w - n
    if z > 9223372036854775807 - len(s):
        raise MemoryError
    r = _rt.str_new(len(s) + z)
    fillrun(r, 0, "0", z)
    _rt.copy(r, z, s, 0, len(s))
    if len(s) > 0 and (_rt.byte(s, 0) == 43 or _rt.byte(s, 0) == 45):
        # a sign moves in front of the zeros
        _rt.str_put(r, 0, _rt.byte(s, 0))
        _rt.str_put(r, z, 48)
    return _rt.str_done(r)


def pys_str_partition(s: str, sep: str) -> tuple[str, str, str]:
    if len(sep) == 0:
        raise ValueError("empty separator")
    i = search(s, sep, 0, len(s)) if len(sep) <= len(s) else -1
    if i < 0:
        return (s, "", "")
    return (s[:i], sep, s[i + len(sep) :])


def pys_str_rpartition(s: str, sep: str) -> tuple[str, str, str]:
    if len(sep) == 0:
        raise ValueError("empty separator")
    i = rsearch(s, sep, 0, len(s))
    if i < 0:
        return ("", "", s)
    return (s[:i], sep, s[i + len(sep) :])


def pys_str_removeprefix(s: str, p: str) -> str:
    if len(p) > 0 and len(s) >= len(p) and _rt.same(s, 0, p, 0, len(p)):
        return s[len(p) :]
    return s


def pys_str_removesuffix(s: str, p: str) -> str:
    if len(p) > 0 and len(s) >= len(p) and _rt.same(s, len(s) - len(p), p, 0, len(p)):
        return s[: len(s) - len(p)]
    return s


def pys_str_expandtabs(s: str, size: int) -> str:
    if size > 2147483647 or size < -2147483648:
        raise OverflowError("Python int too large to convert to C int")  # CPython's C int
    # two passes: the length, then the bytes
    r = _rt.str_new(0)
    for k in range(2):
        col = 0
        at = 0
        for i in range(len(s)):
            c = _rt.byte(s, i)
            if c == 9:
                if size > 0:
                    sp = size - col % size
                    col += sp
                    for _ in range(sp if k == 1 else 0):
                        _rt.str_put(r, at, 32)
                        at += 1
                    at += sp if k == 0 else 0
            else:
                if k == 1:
                    _rt.str_put(r, at, c)
                at += 1
                if c == 10 or c == 13:
                    col = 0
                elif c & 192 != 128:
                    col += 1
        if k == 0:
            r = _rt.str_new(at)
    return _rt.str_done(r)


def pys_str_join(sep: str, l: list[str]) -> str:
    # iterating (no index checks), and a separator of one byte stored as a byte
    m = len(sep)
    n = 0
    i = 0
    for x in l:
        if _rt.null(x):
            # an item of a list[str | None]
            raise TypeError("sequence item " + str(i) + ": expected str instance, NoneType found")
        n += len(x)
        i += 1
    if len(l) > 1:
        n += m * (len(l) - 1)
    r = _rt.str_new(n)
    at = 0
    c = _rt.byte(sep, 0) if m == 1 else -1
    first = True
    for x in l:
        if not first and m > 0:
            if c >= 0:
                _rt.str_put(r, at, c)
            else:
                _rt.copy(r, at, sep, 0, m)
            at += m
        first = False
        _rt.copy(r, at, x, 0, len(x))
        at += len(x)
    return _rt.str_done(r)


def pys_str_split(s: str, sep: str, maxsplit: int) -> list[str]:
    # maxsplit < 0: no limit
    out: list[str] = []
    i = 0
    n = len(s)
    left = maxsplit if maxsplit >= 0 else 9223372036854775807
    if _rt.null(sep):
        while True:
            i = scan_ws(s, i, n, False)
            if i >= n:
                return out
            if left == 0:
                out.append(s[i:])  # the rest, as it is
                return out
            left -= 1
            j = scan_ws(s, i, n, True)
            out.append(s[i:j])
            i = j
    if len(sep) == 0:
        raise ValueError("empty separator")
    c = _rt.byte(sep, 0) if len(sep) == 1 else -1
    dense = False
    while left != 0:
        if c >= 0:
            j = _rt.find_byte(s, c, i, n)  # one byte: memchr, no search setup per part
        else:
            j = again(s, sep, i, n, 0, dense)
            dense = j < -1
            if dense:
                j = -2 - j
        if j < 0:
            break
        left -= 1
        out.append(s[i:j])
        i = j + len(sep)
    out.append(s[i:])
    return out


def pys_str_split_first(s: str, sep: str, maxsplit: int) -> str:
    # s.split(sep, maxsplit)[0] (Gen.index): pys_str_split's first part, without the list or the
    # other parts. Without sep, the first word (none: the list is empty, which [0] raises for)
    n = len(s)
    if _rt.null(sep):
        i = scan_ws(s, 0, n, False)
        if i >= n:
            raise IndexError("list index out of range")
        return s[i:] if maxsplit == 0 else s[i : scan_ws(s, i, n, True)]
    if len(sep) == 0:
        raise ValueError("empty separator")
    j = search(s, sep, 0, n) if maxsplit != 0 else -1
    return s[:j] if j >= 0 else s  # (no sep: s itself, as CPython's list holds it)


def pys_str_rsplit(s: str, sep: str, maxsplit: int) -> list[str]:
    # split from the right; the parts stay in order
    out: list[str] = []
    j = len(s)
    left = maxsplit if maxsplit >= 0 else 9223372036854775807
    if _rt.null(sep):
        while True:
            while j > 0:
                c = _rt.byte(s, _rt.wrap_sub(j, 1))
                b = (1 if ws(c) else -1) if c < 128 else wsback(s, j)
                if b < 0:
                    break
                j = _rt.wrap_sub(j, b)
            if j <= 0:
                break
            if left == 0:
                out.append(s[:j])
                break
            left -= 1
            i = j
            while i > 0:
                c = _rt.byte(s, _rt.wrap_sub(i, 1))
                b = (1 if ws(c) else -1) if c < 128 else wsback(s, i)
                if b > 0:
                    break
                i = _rt.wrap_add(i, b)
            out.append(s[i:j])
            j = i
    else:
        if len(sep) == 0:
            raise ValueError("empty separator")
        while left != 0:
            i = rsearch(s, sep, 0, j)
            if i < 0:
                break
            left -= 1
            out.append(s[i + len(sep) : j])
            j = i
        out.append(s[:j])
    out.reverse()
    return out


def eol(s: str, i: int) -> int:
    # the length of the line break at i, 0 if none
    c = _rt.byte(s, i)
    left = len(s) - i
    if c == 13:
        return 2 if left > 1 and _rt.byte(s, i + 1) == 10 else 1
    if c == 10 or c == 11 or c == 12 or (c >= 28 and c <= 30):
        return 1
    if c == 194 and left > 1 and _rt.byte(s, i + 1) == 133:
        return 2  # U+0085
    if c == 226 and left > 2 and _rt.byte(s, i + 1) == 128 and (_rt.byte(s, i + 2) == 168 or _rt.byte(s, i + 2) == 169):
        return 3  # U+2028, U+2029
    return 0


def pys_str_splitlines(s: str, keep: int) -> list[str]:
    out: list[str] = []
    i = 0
    st = 0
    while i < len(s):
        c = _rt.byte(s, i)
        if c > 30 and c != 194 and c != 226:
            i += 1  # no line break starts with c
            continue
        k = eol(s, i)
        if k == 0:
            i += 1
            continue
        out.append(s[st : i + (k if keep != 0 else 0)])
        i += k
        st = i
    if st < len(s):
        out.append(s[st:])
    return out


# ---------- dict hashing ----------
# The dicts themselves stay in runtime.c (their tables are raw int32 and uint64 arrays), which
# calls these on every lookup; LLVM inlines them there, since the two are one module once
# linked. The arithmetic wraps, as C's unsigned arithmetic does, and the shifts are logical.


def pys_hash_str(s: str) -> int:
    # FNV-1a over the bytes, with the high bits folded into the low ones that pick a slot
    h = 1469598103934665603
    for i in range(len(s)):
        h = _rt.wrap_mul(h ^ _rt.byte(s, i), 1099511628211)
    return h ^ _rt.lshr(h, 29)


def pys_hash_int(k: int) -> int:
    # a round of SplitMix64's mixer (0xBF58476D1CE4E5B9 is -4658895280553007687 as a 64-bit int)
    h = _rt.wrap_mul(k ^ _rt.lshr(k, 30), -4658895280553007687)
    return h ^ _rt.lshr(h, 31)


# ---------- formatting: f"{x:spec}" ----------
# CPython's format-spec mini-language for int (and bool), float and str:
# [[fill]align][sign][z][#][0][width][grouping][.precision][type]. Widths count code points.
# runtime.c's pys_format calls these by the value's type (other types accept only an empty spec),
# and the digits of a float come from runtime.c's pys_fmt_float, which uses snprintf.


def pys_fmt_float(m: float, ty: int, prec: int, alt: int) -> str: ...


def uoff(s: str, k: int) -> int:
    # the byte offset of code point k
    i = 0
    while i < len(s) and k > 0:
        i += 1
        while i < len(s) and _rt.byte(s, i) & 192 == 128:
            i += 1
        k -= 1
    return i


def utf8(c: int) -> str:
    # code point c in UTF-8 (chr(c) is the byte itself below 256)
    if c < 128:
        return chr(c)
    n = 2 if c < 2048 else 3 if c < 65536 else 4
    r = _rt.str_new(n)
    _rt.str_put(r, 0, (c >> 6 * (n - 1)) | (65280 >> n & 255))
    for i in range(1, n):
        _rt.str_put(r, i, 128 | (c >> 6 * (n - 1 - i) & 63))
    return _rt.str_done(r)


def among(c: int, cs: str) -> bool:
    # whether byte c is one of cs, or the end of the spec (0), as strchr finds C's terminator
    return c == 0 or _rt.find_byte(cs, c, 0, len(cs)) >= 0


def ucode(s: str, i: int) -> int:
    # the code point that starts at byte i (a lone or truncated sequence gives what it has)
    c = _rt.byte(s, i)
    if c < 192:
        return c
    n = 1 if c < 224 else 2 if c < 240 else 3
    v = c & (63 >> n)
    for k in range(1, n + 1):
        if i + k < len(s):
            v = (v << 6) | (_rt.byte(s, i + k) & 63)
    return v


def tych(c: int) -> str:
    # a presentation type in a message, as CPython writes it: '\\x%x' outside 33..127
    if c > 32 and c < 128:
        return chr(c)
    h = ""
    q = c
    while True:
        h = "0123456789abcdef"[q % 16] + h
        q = q // 16
        if q == 0:
            break
    return "\\x" + h


def known(c: int, cs: str) -> bool:
    # whether code point c is one of the ASCII codes cs
    return c > 0 and c < 128 and _rt.find_byte(cs, c, 0, len(cs)) >= 0


def tyname(kind: int) -> str:
    return "int" if kind == 0 else "bool" if kind == 1 else "float" if kind == 2 else "str"


def group(dg: str, sep: int, every: int, minw: int) -> str:
    # digits with a separator every `every` of them, zero-padded (separators included) to minw
    n = len(dg)
    z = 0
    total = n + ((n - 1) // every if sep != 0 else 0)
    while total < minw:
        z += 1
        total = n + z + ((n + z - 1) // every if sep != 0 else 0)
    r = _rt.str_new(total)
    at = 0
    for i in range(n + z):
        _rt.str_put(r, at, 48 if i < z else _rt.byte(dg, i - z))
        at += 1
        if sep != 0 and (n + z - i - 1) % every == 0 and i < n + z - 1:
            _rt.str_put(r, at, sep)
            at += 1
    return _rt.str_done(r)


def zero(t: str) -> bool:
    # whether the digits of t, up to an exponent or %, are all zero
    for i in range(len(t)):
        c = _rt.byte(t, i)
        if c == 101 or c == 69 or c == 37:
            return True
        if c >= 49 and c <= 57:
            return False
    return True


def fmt(kind: int, iv: int, fv: float, sv: str, spec: str) -> str:
    # kind: 0 int, 1 bool, 2 float, 3 str (iv, fv or sv is the value)
    n = len(spec)
    p = 0
    fill = " "
    align = 0
    fillset = False
    cl = uoff(spec, 1)
    if cl > 0 and cl < n and _rt.byte(spec, cl) != 0 and among(_rt.byte(spec, cl), "<>=^"):
        fill = spec[:cl]
        fillset = True
        align = _rt.byte(spec, cl)
        p = cl + 1
    elif n > 0 and _rt.byte(spec, 0) != 0 and among(_rt.byte(spec, 0), "<>=^"):
        align = _rt.byte(spec, 0)
        p = 1
    sign = 0
    if p < n and (_rt.byte(spec, p) == 43 or _rt.byte(spec, p) == 45 or _rt.byte(spec, p) == 32):
        sign = _rt.byte(spec, p)
        p += 1
    zneg = False
    if p < n and _rt.byte(spec, p) == 122:
        zneg = True
        p += 1
    alt = False
    if p < n and _rt.byte(spec, p) == 35:
        alt = True
        p += 1
    numeric = kind != 3
    if p < n and _rt.byte(spec, p) == 48:
        # zero padding: fill '0', and '=' alignment for numbers
        if not fillset:
            fill = "0"
            if align == 0 and numeric:
                align = 61
        p += 1
    width = 0
    while p < n and digit(_rt.byte(spec, p)):
        width = width * 10 + _rt.byte(spec, p) - 48
        p += 1
        if width > 100000000:
            raise ValueError("Too many decimal digits in format string")
    sep = 0  # ',' then '_', as CPython reads them: a second ',' or '_' is the type, which it rejects below
    if p < n and _rt.byte(spec, p) == 44:
        sep = 44
        p += 1
    if p < n and _rt.byte(spec, p) == 95:
        if sep != 0:
            raise ValueError("Cannot specify both ',' and '_'.")
        sep = 95
        p += 1
    if p < n and _rt.byte(spec, p) == 44 and sep == 95:
        raise ValueError("Cannot specify both ',' and '_'.")
    prec = -1
    if p < n and _rt.byte(spec, p) == 46:
        p += 1
        if p >= n or not digit(_rt.byte(spec, p)):
            raise ValueError("Format specifier missing precision")
        prec = 0
        while p < n and digit(_rt.byte(spec, p)):
            prec = prec * 10 + _rt.byte(spec, p) - 48
            p += 1
            if prec > 100000000:
                raise ValueError("Too many decimal digits in format string")
    if n - p > 1 and ulen(spec[p:]) > 1:
        raise ValueError(f"Invalid format specifier '{spec}' for object of type '{tyname(kind)}'")
    ty = ucode(spec, p) if p < n else -1  # -1: no type; an explicit NUL is 0
    if ty < 0 and kind == 3:
        ty = 115
    if ty < 0 and kind != 2:
        ty = 100
    if kind == 2 and ty < 0:
        ty = 0  # a float's default type is NUL, as in CPython
    if sep != 0 and ty != 0 and not known(ty, "defgEFG%") and not (sep == 95 and known(ty, "boxX")):
        raise ValueError(f"Cannot specify '{chr(sep)}' with '{tych(ty)}'.")
    body = ""
    pre = 0  # bytes of sign and prefix, before '=' padding
    if kind == 3:
        if ty != 115:
            raise ValueError(f"Unknown format code '{tych(ty)}' for object of type 'str'")
        if sign != 0:
            raise ValueError("Space not allowed in string format specifier" if sign == 32 else "Sign not allowed in string format specifier")
        if zneg:
            raise ValueError("Negative zero coercion (z) not allowed in string format specifier")
        if alt:
            raise ValueError("Alternate form (#) not allowed in string format specifier")
        if align == 61:
            raise ValueError("'=' alignment not allowed in string format specifier")
        body = sv[: uoff(sv, prec)] if prec >= 0 else sv
    elif kind <= 1 and known(ty, "bcdoxXn"):
        if prec >= 0:
            raise ValueError("Precision not allowed in integer format specifier")
        if zneg:
            raise ValueError("Negative zero coercion (z) not allowed in integer format specifier")
        if ty == 99:
            if sign != 0:
                raise ValueError("Sign not allowed with integer format specifier 'c'")
            if alt:
                raise ValueError("Alternate form (#) not allowed with integer format specifier 'c'")
            if iv < 0 or iv > 1114111:
                raise OverflowError("%c arg not in range(0x110000)")
            body = utf8(iv)
        else:
            base = 2 if ty == 98 else 8 if ty == 111 else 16 if ty == 120 or ty == 88 else 10
            hexd = "0123456789ABCDEF" if ty == 88 else "0123456789abcdef"
            u = _rt.wrap_sub(0, iv) if iv < 0 else iv  # |iv| as an unsigned 64-bit pattern
            nd = 0
            q = u
            while True:
                nd += 1
                q = _rt.udiv(q, base)
                if q == 0:
                    break
            dg = _rt.str_new(nd)
            for i in range(nd):
                _rt.str_put(dg, nd - 1 - i, _rt.byte(hexd, _rt.urem(u, base)))
                u = _rt.udiv(u, base)
            head = "-" if iv < 0 else chr(sign) if sign == 43 or sign == 32 else ""
            if alt and base != 10:
                head = head + "0" + ("X" if ty == 88 else "x" if ty == 120 else chr(ty))
            pre = len(head)
            minw = width - pre if fill == "0" and align == 61 else 0
            body = head + group(_rt.str_done(dg), sep, 3 if base == 10 else 4, minw)
    else:
        # a float, or an int with a float type
        x = fv if kind == 2 else float(iv)
        if (ty != 0 or kind != 2) and not known(ty, "eEfFgGn%"):
            raise ValueError(f"Unknown format code '{tych(ty)}' for object of type '{tyname(kind)}'")
        neg = math.copysign(1.0, x) < 0.0 and not math.isnan(x)
        m = -x if neg else x
        t = pys_fmt_float(m, ty, prec, 1 if alt else 0)
        if zneg and neg and not math.isinf(m) and zero(t):
            neg = False  # z: no "-0" after rounding
        head = "-" if neg else chr(sign) if sign == 43 or sign == 32 else ""
        pre = len(head)
        ip = 0  # the integer digits
        while ip < len(t) and digit(_rt.byte(t, ip)):
            ip += 1
        minw = width - pre - (len(t) - ip) if fill == "0" and align == 61 else 0
        body = head + (group(t[:ip], sep, 3, minw) if ip > 0 else "0" * minw) + t[ip:]
    if align == 0:
        align = 62 if numeric else 60
    ln = ulen(body)
    if ln >= width:
        return body
    gap = width - ln
    f = len(fill)
    if gap > (9223372036854775807 - len(body)) // f:
        raise MemoryError
    # the result is built in place, with '=' padding after the sign and prefix (pre)
    left = 0 if align == 60 else gap // 2 if align == 94 else gap
    hd = pre if align == 61 else 0
    r = _rt.str_new(len(body) + gap * f)
    _rt.copy(r, 0, body, 0, hd)
    fillrun(r, hd, fill, left)
    _rt.copy(r, hd + left * f, body, hd, len(body) - hd)
    fillrun(r, left * f + len(body), fill, gap - left)
    return _rt.str_done(r)


def pys_format_str(s: str, spec: str) -> str:
    return fmt(3, 0, 0.0, s, spec)


def pys_format_int(v: int, isbool: int, spec: str) -> str:
    return fmt(1 if isbool != 0 else 0, v, 0.0, "", spec)


def pys_format_float(x: float, spec: str) -> str:
    return fmt(2, 0, x, "", spec)


# ---------- bytes ----------
# A bytes object is a Str, its bytes a str's (see bytes in runtime.c), so its parameters here are
# strs. These are its operations: under names of their own where a str's does the same to the
# bytes (searches, replace, a split at a separator), and apart where a bytes differs: its items
# are ints, its whitespace, case and digits are ASCII's, and its widths count bytes
def ascii_ws(c: int) -> bool:
    # a bytes's whitespace: space, \t, \n, \v, \f and \r
    return c == 32 or (c >= 9 and c <= 13)


def pys_bytes_has(b: str, x: int) -> int:
    # x in b, of an int x: a byte of b with that value
    if x < 0 or x > 255:
        raise ValueError("byte must be in range(0, 256)")
    for i in range(len(b)):
        if _rt.byte(b, i) == x:
            return 1
    return 0


def pys_bytes_contains(h: str, n: str) -> int:
    return pys_str_contains(h, n)


def pys_bytes_find(h: str, n: str, st: int, en: int) -> int:
    return pys_str_find(h, n, st, en)


def pys_bytes_rfind(h: str, n: str, st: int, en: int) -> int:
    return pys_str_rfind(h, n, st, en)


def pys_bytes_count(h: str, n: str, st: int, en: int) -> int:
    return pys_str_count(h, n, st, en)


def pys_bytes_index(h: str, n: str, st: int, en: int) -> int:
    i = pys_str_find(h, n, st, en)
    if i < 0:
        raise ValueError("subsection not found")
    return i


def pys_bytes_rindex(h: str, n: str, st: int, en: int) -> int:
    i = pys_str_rfind(h, n, st, en)
    if i < 0:
        raise ValueError("subsection not found")
    return i


def pys_bytes_startswith(h: str, n: str, st: int, en: int) -> int:
    return pys_str_startswith(h, n, st, en)


def pys_bytes_endswith(h: str, n: str, st: int, en: int) -> int:
    return pys_str_endswith(h, n, st, en)


def pys_bytes_replace(s: str, a: str, b: str) -> str:
    return pys_str_replace(s, a, b)


def pys_bytes_replace_count(s: str, a: str, b: str, n: int) -> str:
    return pys_str_replace_count(s, a, b, n)


def pys_bytes_partition(s: str, sep: str) -> tuple[str, str, str]:
    return pys_str_partition(s, sep)


def pys_bytes_rpartition(s: str, sep: str) -> tuple[str, str, str]:
    return pys_str_rpartition(s, sep)


def pys_bytes_removeprefix(s: str, p: str) -> str:
    return pys_str_removeprefix(s, p)


def pys_bytes_removesuffix(s: str, p: str) -> str:
    return pys_str_removesuffix(s, p)


def pys_bytes_join(sep: str, l: list[str]) -> str:
    for i in range(len(l)):
        if _rt.null(l[i]):
            # (an item of a list[bytes | None]: CPython's TypeError names a bytes-like object)
            raise TypeError("sequence item " + str(i) + ": expected a bytes-like object, NoneType found")
    return pys_str_join(sep, l)


def ws_split(s: str, maxsplit: int, right: bool) -> list[str]:
    # s.split() or s.rsplit() of a bytes, at runs of ASCII whitespace; past maxsplit parts (when
    # it is not negative) the rest is one part, its whitespace at the far end kept
    out: list[str] = []
    n = len(s)
    left = maxsplit if maxsplit >= 0 else 9223372036854775807
    if not right:
        i = 0
        while True:
            while i < n and ascii_ws(_rt.byte(s, i)):
                i += 1
            if i >= n:
                return out
            if left == 0:
                out.append(s[i:])
                return out
            left -= 1
            j = i
            while j < n and not ascii_ws(_rt.byte(s, j)):
                j += 1
            out.append(s[i:j])
            i = j
    j = n
    while True:
        while j > 0 and ascii_ws(_rt.byte(s, j - 1)):
            j -= 1
        if j <= 0:
            break
        if left == 0:
            out.append(s[:j])
            break
        left -= 1
        i = j
        while i > 0 and not ascii_ws(_rt.byte(s, i - 1)):
            i -= 1
        out.append(s[i:j])
        j = i
    out.reverse()
    return out


def pys_bytes_split(s: str, sep: str, maxsplit: int) -> list[str]:
    if _rt.null(sep):
        return ws_split(s, maxsplit, False)
    return pys_str_split(s, sep, maxsplit)


def pys_bytes_rsplit(s: str, sep: str, maxsplit: int) -> list[str]:
    if _rt.null(sep):
        return ws_split(s, maxsplit, True)
    return pys_str_rsplit(s, sep, maxsplit)


def bstrip(s: str, cs: str, m: int) -> str:
    # m: 1 left, 2 right, 3 both; the bytes of cs (ASCII whitespace where cs is null)
    i = 0
    j = len(s)
    if m & 1:
        while i < j and (ascii_ws(_rt.byte(s, i)) if _rt.null(cs) else _rt.find_byte(cs, _rt.byte(s, i), 0, len(cs)) >= 0):
            i += 1
    if m & 2:
        while j > i and (ascii_ws(_rt.byte(s, j - 1)) if _rt.null(cs) else _rt.find_byte(cs, _rt.byte(s, j - 1), 0, len(cs)) >= 0):
            j -= 1
    return s[i:j]


def pys_bytes_strip(s: str, cs: str) -> str:
    return bstrip(s, cs, 3)


def pys_bytes_lstrip(s: str, cs: str) -> str:
    return bstrip(s, cs, 1)


def pys_bytes_rstrip(s: str, cs: str) -> str:
    return bstrip(s, cs, 2)


def pys_bytes_upper(s: str) -> str:
    return mapcase(s, 1)


def pys_bytes_lower(s: str) -> str:
    return mapcase(s, 0)


def pys_bytes_swapcase(s: str) -> str:
    return mapcase(s, 2)


def pys_bytes_capitalize(s: str) -> str:
    r = _rt.str_new(len(s))
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if (i == 0 and lowc(c)) or (i > 0 and upc(c)):
            c ^= 32
        _rt.str_put(r, i, c)
    return _rt.str_done(r)


def bclass(s: str, k: int) -> int:
    # every byte of s (and there is one) an ASCII letter (k 1), letter or digit (2), digit (0),
    # or whitespace (3)
    if len(s) == 0:
        return 0
    for i in range(len(s)):
        c = _rt.byte(s, i)
        ok = ascii_ws(c) if k == 3 else digit(c) or (k > 0 and (lowc(c) or upc(c))) if k == 2 else digit(c) if k == 0 else lowc(c) or upc(c)
        if not ok:
            return 0
    return 1


def pys_bytes_isalpha(s: str) -> int:
    return bclass(s, 1)


def pys_bytes_isalnum(s: str) -> int:
    return bclass(s, 2)


def pys_bytes_isdigit(s: str) -> int:
    return bclass(s, 0)


def pys_bytes_isspace(s: str) -> int:
    return bclass(s, 3)


def bcased(s: str, up: bool) -> int:
    # b.isupper() (up) or b.islower(): a cased ASCII letter, and none of the other case
    cased = False
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if (lowc(c) and up) or (upc(c) and not up):
            return 0
        cased = cased or lowc(c) or upc(c)
    return 1 if cased else 0


def pys_bytes_isupper(s: str) -> int:
    return bcased(s, True)


def pys_bytes_islower(s: str) -> int:
    return bcased(s, False)


def pys_bytes_isascii(s: str) -> int:
    return pys_str_isascii(s)


def bpad(s: str, w: int, fill: str, how: int, name: str) -> str:
    # how: 0 right, 1 left, 2 center; widths count bytes; fill is null for a space, else one byte
    if not _rt.null(fill) and len(fill) != 1:
        raise TypeError(name + "() argument 2 must be a byte string of length 1, not bytes")
    c = 32 if _rt.null(fill) else _rt.byte(fill, 0)
    if len(s) >= w:
        return s
    gap = w - len(s)
    left = 0 if how == 1 else gap if how == 0 else gap // 2 + (gap & w & 1)  # CPython's centering
    r = _rt.str_new(w)
    for i in range(left):
        _rt.str_put(r, i, c)
    _rt.copy(r, left, s, 0, len(s))
    for i in range(left + len(s), w):
        _rt.str_put(r, i, c)
    return _rt.str_done(r)


def pys_bytes_ljust(s: str, w: int, fill: str) -> str:
    return bpad(s, w, fill, 1, "ljust")


def pys_bytes_rjust(s: str, w: int, fill: str) -> str:
    return bpad(s, w, fill, 0, "rjust")


def pys_bytes_center(s: str, w: int, fill: str) -> str:
    return bpad(s, w, fill, 2, "center")


def pys_bytes_zfill(s: str, w: int) -> str:
    if len(s) >= w:
        return s
    z = w - len(s)
    r = _rt.str_new(w)
    for i in range(z):
        _rt.str_put(r, i, 48)
    _rt.copy(r, z, s, 0, len(s))
    if len(s) > 0 and (_rt.byte(s, 0) == 43 or _rt.byte(s, 0) == 45):
        # a sign moves in front of the zeros
        _rt.str_put(r, 0, _rt.byte(s, 0))
        _rt.str_put(r, z, 48)
    return _rt.str_done(r)


def pys_bytes_splitlines(s: str, keep: int) -> list[str]:
    # the lines of a bytes end at \n, \r or \r\n only
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        j = i
        while j < n and _rt.byte(s, j) != 10 and _rt.byte(s, j) != 13:
            j += 1
        e = j
        if j < n:
            e = j + 2 if _rt.byte(s, j) == 13 and j + 1 < n and _rt.byte(s, j + 1) == 10 else j + 1
        out.append(s[i:e] if keep else s[i:j])
        i = e
    return out


def pys_bytes_hex(s: str) -> str:
    r = _rt.str_new(2 * len(s))
    for i in range(len(s)):
        c = _rt.byte(s, i)
        _rt.str_put(r, 2 * i, (48 if c >> 4 < 10 else 87) + (c >> 4))
        _rt.str_put(r, 2 * i + 1, (48 if c & 15 < 10 else 87) + (c & 15))
    return _rt.str_done(r)


def pys_bytes_hex_sep(s: str, sep: str, chars: int, per: int) -> str:
    # s.hex(sep, per) as CPython's (Python/pystrhex.c): sep (null: none), one ASCII character of a
    # str (chars 1) or byte of a bytes, between the groups of per bytes, which count from the
    # right where per is positive, from the left where it is negative (no groups where it is 0)
    if per > 2147483647 or per < -2147483648:
        raise OverflowError("Python int too large to convert to C int")  # (a C int argument)
    if _rt.null(sep):
        return pys_bytes_hex(s)
    k = len(sep)
    if chars == 1:
        k = 0
        i = 0
        while i < len(sep):
            i += u8seq(sep, i, len(sep))
            k += 1
    if k != 1:
        raise ValueError("sep must be length 1.")
    c = _rt.byte(sep, 0)
    if c > 127:
        raise ValueError("sep must be ASCII.")
    n = len(s)
    g = per if per >= 0 else -per
    r = _rt.str_new(2 * n + ((n - 1) // g if g > 0 and n > 0 else 0))
    j = 0
    for i in range(n):
        if g > 0 and i > 0 and ((per > 0 and (n - i) % g == 0) or (per < 0 and i % g == 0)):
            _rt.str_put(r, j, c)
            j += 1
        b = _rt.byte(s, i)
        _rt.str_put(r, j, (48 if b >> 4 < 10 else 87) + (b >> 4))
        _rt.str_put(r, j + 1, (48 if b & 15 < 10 else 87) + (b & 15))
        j += 2
    return _rt.str_done(r)


def pys_bytes_maketrans(frm: str, to: str) -> str:
    # bytes.maketrans(frm, to): the 256 bytes that map each byte of frm to the byte of to in its
    # place (the last, for a byte frm holds twice), and every other byte to itself
    if len(frm) != len(to):
        raise ValueError("maketrans arguments must have same length")
    r = _rt.str_new(256)
    for i in range(256):
        _rt.str_put(r, i, i)
    for i in range(len(frm)):
        _rt.str_put(r, _rt.byte(frm, i), _rt.byte(to, i))
    return _rt.str_done(r)


def pys_bytes_translate(s: str, table: str, delete: str) -> str:
    # s.translate(table, delete): the bytes of s that delete (null: b"") does not hold, each
    # mapped by table, 256 bytes (null: None, which maps none)
    if not _rt.null(table) and len(table) != 256:
        raise ValueError("translation table must be 256 characters long")
    n = len(s)
    keep = n
    if not _rt.null(delete) and len(delete) > 0:
        keep = 0
        for i in range(n):
            if _rt.find_byte(delete, _rt.byte(s, i), 0, len(delete)) < 0:
                keep += 1
    r = _rt.str_new(keep)
    j = 0
    for i in range(n):
        c = _rt.byte(s, i)
        if keep < n and _rt.find_byte(delete, c, 0, len(delete)) >= 0:
            continue
        _rt.str_put(r, j, c if _rt.null(table) else _rt.byte(table, c))
        j += 1
    return _rt.str_done(r)


def hexval(c: int) -> int:
    return c - 48 if digit(c) else c - 87 if c >= 97 and c <= 102 else c - 55 if c >= 65 and c <= 70 else -1


def pys_bytes_fromhex(s: str) -> str:
    # bytes.fromhex(s): pairs of hexadecimal digits, ASCII whitespace between them
    out: list[int] = []
    i = 0
    n = len(s)
    while True:
        while i < n and ascii_ws(_rt.byte(s, i)):
            i += 1
        if i >= n:
            break
        hi = hexval(_rt.byte(s, i))
        lo = hexval(_rt.byte(s, i + 1)) if i + 1 < n else -1
        if hi < 0 or lo < 0:
            raise ValueError("non-hexadecimal number found in fromhex() arg at position " + str(i if hi < 0 else i + 1))
        out.append(hi * 16 + lo)
        i += 2
    return pys_bytes_from_list(out)


def pys_bytes_from_list(xs: list[int]) -> str:
    # bytes(xs) of a list of ints
    r = _rt.str_new(len(xs))
    for i in range(len(xs)):
        if xs[i] < 0 or xs[i] > 255:
            raise ValueError("bytes must be in range(0, 256)")
        _rt.str_put(r, i, xs[i])
    return _rt.str_done(r)


def pys_bytes_zeros(n: int) -> str:
    # bytes(n): n zero bytes
    if n < 0:
        raise ValueError("negative count")
    return _rt.str_done(_rt.str_new(n))


# ---- codecs: str.encode() and bytes.decode() with CPython's UTF-8, Latin-1 and ASCII codecs
# and error handlers. A str holds UTF-8, where a surrogate is its three bytes (ED A0 80 to ED BF
# BF, which decode with "surrogateescape" or "surrogatepass" makes)
def codec_of(encoding: str) -> int:
    # the codec an encoding names, as codecs.lookup() finds it among encodings.aliases: 0 UTF-8,
    # 1 Latin-1, 2 ASCII, else CPython's LookupError. The name is normalized as
    # encodings.normalize_encoding does: lower case, other characters than letters, digits and
    # '.' one '_' between the parts
    norm = ""
    punct = False
    for i in range(len(encoding)):
        c = _rt.byte(encoding, i)
        if digit(c) or lowc(c) or upc(c) or c == 46:
            if punct and len(norm) > 0:
                norm += "_"
            norm += chr(c | 32 if upc(c) else c)
            punct = False
        else:
            punct = True
    alias = norm.replace(".", "_")
    for nm in [norm, alias]:
        if nm in ["utf_8", "cp65001", "u8", "utf", "utf8", "utf8_ucs2", "utf8_ucs4"]:
            return 0
        if nm in ["latin_1", "8859", "cp819", "csisolatin1", "ibm819", "iso8859", "iso8859_1", "iso_8859_1",
                  "iso_8859_1_1987", "iso_ir_100", "l1", "latin", "latin1"]:
            return 1
        if nm in ["ascii", "646", "ansi_x3.4_1968", "ansi_x3.4_1986", "ansi_x3_4_1968", "cp367", "csascii",
                  "ibm367", "iso646_us", "iso_646.irv_1991", "iso_ir_6", "us", "us_ascii"]:
            return 2
    raise LookupError("unknown encoding: " + encoding)


def codec_name(k: int) -> str:
    return "utf-8" if k == 0 else "latin-1" if k == 1 else "ascii"


def u8seq(s: str, i: int, n: int) -> int:
    # the length of the UTF-8 character at s[i] (a surrogate's three bytes are one), as a str
    # holds it; 1 for a byte that begins none
    c = _rt.byte(s, i)
    if c < 0xC2 or c > 0xF4:
        return 1
    k = 2 if c < 0xE0 else 3 if c < 0xF0 else 4
    if i + k > n:
        return 1
    for j in range(i + 1, i + k):
        if _rt.byte(s, j) & 0xC0 != 0x80:
            return 1
    return k


def u8cp(s: str, i: int, k: int) -> int:
    # the code point of the k bytes of UTF-8 at s[i] (k 1: the byte)
    if k == 1:
        return _rt.byte(s, i)
    v = _rt.byte(s, i) & (0x1F if k == 2 else 0x0F if k == 3 else 0x07)
    for j in range(i + 1, i + k):
        v = (v << 6) | (_rt.byte(s, j) & 0x3F)
    return v


def u8put(out: list[str], cp: int) -> None:
    # the UTF-8 bytes of code point cp (a surrogate's too), each as chr() writes a byte
    if cp < 0x80:
        out.append(chr(cp))
    elif cp < 0x800:
        out.append(chr(0xC0 | (cp >> 6)) + chr(0x80 | (cp & 0x3F)))
    elif cp < 0x10000:
        out.append(chr(0xE0 | (cp >> 12)) + chr(0x80 | ((cp >> 6) & 0x3F)) + chr(0x80 | (cp & 0x3F)))
    else:
        out.append(chr(0xF0 | (cp >> 18)) + chr(0x80 | ((cp >> 12) & 0x3F)) + chr(0x80 | ((cp >> 6) & 0x3F)) + chr(0x80 | (cp & 0x3F)))


def hexpart(v: int, n: int) -> str:
    # v as n lower-case hexadecimal digits
    r = _rt.str_new(n)
    for i in range(n):
        d = (v >> (4 * (n - 1 - i))) & 15
        _rt.str_put(r, i, (48 if d < 10 else 87) + d)
    return _rt.str_done(r)


def escaped(cp: int) -> str:
    # \xNN, \uNNNN or \UNNNNNNNN, as CPython's UnicodeEncodeError message and "backslashreplace"
    # write a code point
    return "\\x" + hexpart(cp, 2) if cp < 0x100 else "\\u" + hexpart(cp, 4) if cp < 0x10000 else "\\U" + hexpart(cp, 8)


def pys_str_encode(s: str, encoding: str, errors: str) -> str:
    # s.encode(encoding, errors): the bytes; the characters the codec cannot encode (a surrogate
    # in UTF-8, above U+00FF or U+007F) go to the error handler in runs, as CPython gives them.
    # An omitted (null) encoding is UTF-8, omitted errors "strict"
    k = 0 if _rt.null(encoding) else codec_of(encoding)
    if _rt.null(errors):
        errors = "strict"
    if pys_str_isascii(s) == 1 or (k == 0 and _rt.find_byte(s, 0xED, 0, len(s)) < 0):
        return s  # (only ED begins a surrogate's bytes)
    limit = 0x80 if k == 2 else 0x100 if k == 1 else 0x110000
    out: list[str] = []
    n = len(s)
    i = 0
    start = 0
    pos = 0  # out holds the bytes of s[:start]; s[:i] holds pos characters
    while i < n:
        m = u8seq(s, i, n)
        cp = u8cp(s, i, m)
        surr = cp >= 0xD800 and cp <= 0xDFFF and m == 3
        if cp < 0x80 or (k == 0 and not surr):
            i += m
            pos += 1
            continue
        out.append(s[start:i])
        if cp < limit and not surr:
            out.append(chr(cp))  # (Latin-1: the byte)
            i += m
            pos += 1
            start = i
            continue
        first = pos
        cps: list[int] = []
        while i < n:
            m = u8seq(s, i, n)
            cp = u8cp(s, i, m)
            surr = cp >= 0xD800 and cp <= 0xDFFF and m == 3
            if cp < limit and not surr:
                break
            cps.append(cp)
            i += m
            pos += 1
        out.append(encode_error(cps, first, k, errors))
        start = i
    out.append(s[start:])
    return "".join(out)


def pys_unicode_error_str(dec: int, encoding: str, obj: str, start: int, end: int, reason: str) -> str:
    # str() of UnicodeDecodeError(encoding, obj, start, end, reason) (dec 1: obj a bytes) or of
    # UnicodeEncodeError(...) (obj a str, whose characters start and end count), as CPython's
    # (Objects/exceptions.c): the one byte or character at start, or the range to end
    n = len(obj)
    if dec == 1:
        if start >= 0 and start < n and end >= 0 and end <= n and end == start + 1:
            return "'" + encoding + "' codec can't decode byte 0x" + hexpart(_rt.byte(obj, start), 2) + " in position " + str(start) + ": " + reason
        return "'" + encoding + "' codec can't decode bytes in position " + str(start) + "-" + str(end - 1) + ": " + reason
    i = 0
    chars = 0
    bad = 0
    while i < n:
        m = u8seq(obj, i, n)
        if chars == start:
            bad = u8cp(obj, i, m)
        i += m
        chars += 1
    if start >= 0 and start < chars and end >= 0 and end <= chars and end == start + 1:
        return "'" + encoding + "' codec can't encode character '" + escaped(bad) + "' in position " + str(start) + ": " + reason
    return "'" + encoding + "' codec can't encode characters in position " + str(start) + "-" + str(end - 1) + ": " + reason


def encode_error(cps: list[int], pos: int, k: int, errors: str) -> str:
    # the bytes error handler errors makes of code points cps, from character pos of the str on,
    # which codec k cannot encode, as CPython's handlers make them
    if errors == "replace":
        return "?" * len(cps)
    if errors == "ignore":
        return ""
    out: list[str] = []
    if errors == "backslashreplace":
        for cp in cps:
            out.append(escaped(cp))
        return "".join(out)
    if errors == "xmlcharrefreplace":
        for cp in cps:
            out.append("&#" + str(cp) + ";")
        return "".join(out)
    j = 0
    if errors == "surrogateescape":
        while j < len(cps) and cps[j] >= 0xDC80 and cps[j] <= 0xDCFF:
            j += 1
        if j == len(cps):
            for cp in cps:
                out.append(chr(cp - 0xDC00))
            return "".join(out)
    elif errors == "surrogatepass" and k == 0:
        for cp in cps:
            u8put(out, cp)
        return "".join(out)
    elif errors != "strict" and errors != "surrogatepass":
        raise LookupError("unknown error handler name '" + errors + "'")
    start = pos + j
    end = pos + len(cps)
    reason = "surrogates not allowed" if k == 0 else "ordinal not in range(256)" if k == 1 else "ordinal not in range(128)"
    if end - start == 1:
        _rt.fail("UnicodeEncodeError", "'" + codec_name(k) + "' codec can't encode character '" + escaped(cps[j]) + "' in position " + str(start) + ": " + reason)
    _rt.fail("UnicodeEncodeError", "'" + codec_name(k) + "' codec can't encode characters in position " + str(start) + "-" + str(end - 1) + ": " + reason)
    return ""


def u8char(b: str, i: int, n: int) -> int:
    # the length of the UTF-8 character at b[i], as CPython's decoder reads it (stringlib's
    # utf8_decode), or 0 where the bytes from i on are none (u8bad tells why, and how many)
    c = _rt.byte(b, i)
    if c < 0xC2 or c > 0xF4:
        return 0
    k = 2 if c < 0xE0 else 3 if c < 0xF0 else 4
    lo = 0xA0 if c == 0xE0 else 0x90 if c == 0xF0 else 0x80
    hi = 0x9F if c == 0xED else 0x8F if c == 0xF4 else 0xBF
    for j in range(i + 1, i + k):
        if j >= n:
            return 0
        d = _rt.byte(b, j)
        if d < lo or d > hi:
            return 0
        lo = 0x80
        hi = 0xBF
    return k


def u8bad(b: str, i: int, n: int) -> int:
    # where the bytes from b[i] on that are no character end (u8char 0), as CPython's decoder
    # gives them to the error handler; minus that end where the data ends first
    c = _rt.byte(b, i)
    if c < 0xC2 or c > 0xF4:
        return i + 1  # (invalid start byte)
    k = 2 if c < 0xE0 else 3 if c < 0xF0 else 4
    lo = 0xA0 if c == 0xE0 else 0x90 if c == 0xF0 else 0x80
    hi = 0x9F if c == 0xED else 0x8F if c == 0xF4 else 0xBF
    for j in range(i + 1, i + k):
        if j >= n:
            return -n  # (unexpected end of data)
        d = _rt.byte(b, j)
        if d < lo or d > hi:
            return j  # (invalid continuation byte)
        lo = 0x80
        hi = 0xBF
    return i + k


def pys_bytes_decode(b: str, encoding: str, errors: str) -> str:
    # b.decode(encoding, errors): the str; the bytes the codec cannot decode go to the error
    # handler as CPython's decoder gives them (an omitted encoding is UTF-8, as in encode). An
    # empty b is the empty str whatever its encoding names: CPython looks no codec up for it
    if len(b) == 0:
        return b
    k = 0 if _rt.null(encoding) else codec_of(encoding)
    if _rt.null(errors):
        errors = "strict"
    if pys_str_isascii(b) == 1:
        return b
    out: list[str] = []
    n = len(b)
    i = 0
    start = 0  # out holds the characters of b[:start]
    while i < n:
        c = _rt.byte(b, i)
        if c < 0x80:
            i += 1
            continue
        if k == 1:
            out.append(b[start:i])
            u8put(out, c)
            i += 1
            start = i
            continue
        m = u8char(b, i, n) if k == 0 else 0
        if m > 0:
            i += m  # (its bytes are the str's)
            continue
        end = u8bad(b, i, n) if k == 0 else i + 1
        why = "ordinal not in range(128)" if k == 2 else "invalid start byte" if end == i + 1 and (c < 0xC2 or c > 0xF4) else "unexpected end of data" if end < 0 else "invalid continuation byte"
        end = -end if end < 0 else end
        out.append(b[start:i])
        rep = decode_error(b, i, end, k, errors, why)
        out.append(rep[0])
        i = rep[1]
        start = i
    out.append(b[start:])
    return "".join(out)


def decode_error(b: str, start: int, end: int, k: int, errors: str, why: str) -> tuple[str, int]:
    # what error handler errors makes of the bytes b[start:end], which codec k cannot decode (for
    # why), and where decoding goes on, as CPython's handlers do
    out: list[str] = []
    if errors == "replace":
        u8put(out, 0xFFFD)
        return ("".join(out), end)
    if errors == "ignore":
        return ("", end)
    if errors == "backslashreplace":
        for j in range(start, end):
            out.append("\\x" + hexpart(_rt.byte(b, j), 2))
        return ("".join(out), end)
    if errors == "surrogateescape":
        for j in range(start, end):
            u8put(out, 0xDC00 + _rt.byte(b, j))
        return ("".join(out), end)
    if errors == "surrogatepass" and k == 0 and len(b) - start >= 3:
        b1 = _rt.byte(b, start)
        b2 = _rt.byte(b, start + 1)
        b3 = _rt.byte(b, start + 2)
        cp = ((b1 & 0x0F) << 12) | ((b2 & 0x3F) << 6) | (b3 & 0x3F)
        if b1 & 0xF0 == 0xE0 and b2 & 0xC0 == 0x80 and b3 & 0xC0 == 0x80 and cp >= 0xD800 and cp <= 0xDFFF:
            return (b[start : start + 3], start + 3)  # (a surrogate's three bytes, as a str holds it)
    if errors == "xmlcharrefreplace" or errors == "namereplace":
        raise TypeError("don't know how to handle UnicodeDecodeError in error callback")
    if errors != "strict" and errors != "surrogatepass":
        raise LookupError("unknown error handler name '" + errors + "'")
    if end - start == 1:
        _rt.fail("UnicodeDecodeError", "'" + codec_name(k) + "' codec can't decode byte 0x" + hexpart(_rt.byte(b, start), 2) + " in position " + str(start) + ": " + why)
    _rt.fail("UnicodeDecodeError", "'" + codec_name(k) + "' codec can't decode bytes in position " + str(start) + "-" + str(end - 1) + ": " + why)
    return ("", end)
