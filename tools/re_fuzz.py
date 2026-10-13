"""Differential fuzzing of lib/re on CPython, against CPython's own re (and its _sre engine).

lib/re is ordinary Python, so CPython runs it as a package of its own (pys_re here). Random
patterns, from a grammar of 3.13's syntax (classes, the escapes and categories, anchors, greedy,
lazy and possessive repeats, capturing, named, atomic and scoped-flag groups, lookahead and
lookbehind, backreferences, conditionals, inline flags, comments and VERBOSE text, non-ASCII and
case-folding characters), some of them made invalid on purpose, are compiled by both: an invalid
one must raise the same exception with the same message and position, a valid one must compile to
the same code (as CPython's _parser and _compiler make it), with the same groups, group names and
repr. Each valid pattern then runs on 19 random strings of its own characters and a few others:
search(), match() and fullmatch() (also with pos and endpos), findall(), finditer(), split(),
subn() with a template and with a function, and Match.expand(), which must give the same spans,
groups, lastindex and lastgroup, results or exception. The port's documented deviations are
expected where they apply: findall() of 2 groups or more, and a split() whose list would hold None,
raise NotImplementedError (lib/README.md).

Every other pattern runs on Pystachy's strs, which hold UTF-8 (see "the port on Pystachy's strs"
below), the others on CPython's, where the port's positions are code points as CPython's are.
Before them, Lib/test/test_re.py's cases that tests/upstream_re_*.py run smaller or leave out (too
costly with a collection at every allocation, make verify's gc-stress) run here at upstream's
sizes (UPSTREAM). A repeat of a group that holds an unbounded repeat or alternatives is bounded:
unbounded, such patterns backtrack exponentially, in _sre too.

Deterministic: the patterns and strings come from random.Random(SEED). Compiled Pystachy runs the
same port: tests/upstream_re_*.py and tests/lib_re.py check it against CPython's re.

usage: python3 tools/re_fuzz.py [N] [SEED]   (N random patterns, default 2000; SEED default 1)
"""
import importlib.util
import os
import random
import re
import re._compiler
import re._parser
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("pys_re", os.path.join(ROOT, "lib", "re", "__init__.py"),
                                               submodule_search_locations=[os.path.join(ROOT, "lib", "re")])
port = importlib.util.module_from_spec(_spec)
sys.modules["pys_re"] = port
_spec.loader.exec_module(port)
# (CPython's FutureWarning of a possible set operation, "[a--b]": the port has no warnings)
warnings.simplefilter("ignore", FutureWarning)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
R = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
STRINGS = 19  # strings per valid pattern
# characters of patterns and strings: ASCII letters and digits, separators, and non-ASCII ones that
# case-fold in interesting ways (K and the Kelvin sign, s and the long s, sharp s, dotless i, Greek
# sigmas, Cyrillic, a fullwidth digit, an astral letter)
LETTERS = "abcxyzAB"
OTHER = "019 -_.\n"
WIDE = "éÉßKſıσςΣжЖ０𝒜"
fails = 0
cases = 0
patterns = valid = 0


# ---- the patterns

CATEGORIES = ["\\w", "\\W", "\\d", "\\D", "\\s", "\\S"]
ANCHORS = ["^", "$", "\\A", "\\Z", "\\b", "\\B"]


class Gen:
    # one random pattern: the groups it has closed, by number and by name (the ones a
    # backreference or a conditional may name), and a count of its unbounded repeats and
    # alternatives
    def __init__(self):
        self.groups = 0
        self.closed: list[int] = []
        self.names: list[str] = []
        self.loops = 0

    def char(self):
        k = R.randrange(10)
        if k < 6:
            return R.choice(LETTERS)
        if k < 8:
            c = R.choice(OTHER)
            return "\\" + c if c in ".-" and R.randrange(2) else c if c != "\n" else "\\n"
        return R.choice(WIDE)

    def cls(self):
        items = []
        for _ in range(R.randrange(1, 4)):
            k = R.randrange(8)
            if k < 3:
                items.append(R.choice(LETTERS + WIDE))
            elif k < 5:
                a, b = sorted(R.sample("abcxyzABKX0zЖж", 2))
                items.append(a + "-" + b)
            elif k < 7:
                items.append(R.choice(CATEGORIES))
            else:
                items.append(R.choice(["\\]", "\\-", "-", "^", "\\\\", "\\x41", "\\u00e9", "\\n", "\\b", "\\0", "\\101"]))
        return "[" + ("^" if R.randrange(4) == 0 else "") + "".join(items) + "]"

    def group(self, body):
        # a capturing group, named or not, around what body() makes: its number is its opening
        # parenthesis', and a backreference may name it once it is closed
        self.groups += 1
        g = self.groups
        text = body()
        self.closed.append(g)
        if R.randrange(3) == 0:
            self.names.append("g%d" % g)
            return "(?P<g%d>%s)" % (g, text)
        return "(%s)" % text

    def fixed(self):
        # the contents of a lookbehind: of a fixed width (a group may stand there, but no
        # backreference), and once in ten a variable one, or a reference to a group to come
        out = ""
        for _ in range(R.randrange(4)):
            k = R.randrange(10)
            x = self.char() if k < 5 else "." if k < 6 else self.cls() if k < 8 else R.choice(CATEGORIES + ANCHORS)
            if x not in ANCHORS and R.randrange(5) == 0:
                x += "{%d}" % R.randrange(4)
            out += x
        k = R.randrange(10)
        if k < 2:
            return self.group(lambda: out)
        if k < 3:
            # alternatives of one width
            return "(?:%s|%s)" % (out, out.replace("a", "b").replace("x", "yz"[: 1 + R.randrange(2)]))
        if k < 4:
            return out + R.choice(["a*", "|bc", "\\%d" % (self.groups + 1)])
        return out

    def atom(self, depth):
        # an atom, and whether a repeat may follow it
        k = R.randrange(40 if depth < 3 else 18)
        if k < 7:
            return self.char(), True
        if k < 9:
            return ".", True
        if k < 12:
            return self.cls(), True
        if k < 14:
            return R.choice(CATEGORIES), True
        if k < 16:
            return R.choice(ANCHORS), False
        if k < 18:
            # a backreference, by number or name, to a group closed already
            if self.names and R.randrange(3) == 0:
                return "(?P=%s)" % R.choice(self.names), True
            if self.closed:
                return "\\%d" % R.choice(self.closed), True
            return self.char(), True
        if k < 23:
            return self.group(lambda: self.alt(depth + 1)), True
        if k < 26:
            return "(?:%s)" % self.alt(depth + 1), True
        if k < 28:
            return "(?>%s)" % self.alt(depth + 1), True
        if k < 31:
            return "(?%s%s)" % (R.choice(["=", "!"]), self.alt(depth + 1)), True
        if k < 33:
            return "(?%s%s)" % (R.choice(["<=", "<!"]), self.fixed()), True
        if k < 35:
            if not self.closed:
                return self.char(), True
            ref = str(R.choice(self.closed))
            if self.names and R.randrange(3) == 0:
                ref = R.choice(self.names)
            no = "|" + self.seq(depth + 1) if R.randrange(2) else ""
            return "(?(%s)%s%s)" % (ref, self.seq(depth + 1), no), True
        if k < 38:
            on = R.choice(["i", "m", "s", "x", "a", "u", "is", "im"])
            off = R.choice(["", "", "-i", "-s", "-m", "-x"])
            if off[1:] and off[1:] in on:
                off = ""
            return "(?%s%s:%s)" % (on if not off or R.randrange(2) else "", off, self.alt(depth + 1)), True
        return "(?#%s)" % R.choice(["", "c", "x y"]), False

    def piece(self, depth):
        # an atom and maybe a repeat: greedy, lazy or possessive (on an anchor or after a comment,
        # once in 30, CPython's "nothing to repeat" or "multiple repeat"). An atom that holds an
        # unbounded repeat or alternatives gets a bounded one: unbounded, they would backtrack
        # exponentially, in _sre too (and the port is pure Python here)
        loops = self.loops
        a, repeatable = self.atom(depth)
        if R.randrange(3) or not repeatable and R.randrange(30):
            return a
        q = R.choice(["?", "{2}", "{1,3}", "{,2}", "{0}", "{3,1}" if R.randrange(40) == 0 else "{1}"] +
                     (["*", "+", "{2,}"] if self.loops == loops else []))
        if q in ["*", "+", "{2,}"]:
            self.loops += 1
        return a + q + R.choice(["", "", "?", "+"])

    def seq(self, depth):
        return "".join(self.piece(depth) for _ in range(R.randrange(4 if depth else 6)))

    def alt(self, depth):
        out = self.seq(depth)
        while R.randrange(4 if depth else 3) == 0:
            out += "|" + self.seq(depth)
            self.loops += 1
        return out


def pattern():
    g = Gen()
    p = g.alt(0)
    k = R.randrange(15)
    if k == 0:
        p = "(?%s)" % R.choice(["i", "m", "s", "x", "a", "u", "ix", "ims", "L" if R.randrange(4) == 0 else "is"]) + p
    elif k == 1:
        # VERBOSE text: spaces, newlines and comments to skip
        p = "(?x)" + p.replace("a", " a ").replace("b", "b # c\n")
    elif k == 2:
        # a deliberate error (mostly): a character dropped, added or doubled
        i = R.randrange(len(p) + 1)
        c = R.choice("()[]{}?*+|\\^$-:<>=!P#0123")
        p = R.choice([p[:i] + p[i + 1:], p[:i] + c + p[i:], p[:i] + p[i:i + 1] * 2 + p[i + 1:]])
    return p


def flags():
    k = R.randrange(40)
    if k == 0:
        return R.choice([re.L, re.A | re.U, re.L | re.I])  # (ValueErrors for a str pattern)
    return R.choice([0, 0, 0, re.I, re.M, re.S, re.X, re.A, re.U, re.I | re.M, re.I | re.S | re.A, re.I | re.X])


def text(p):
    # a string of the pattern's own letters and some others
    alpha = [c for c in p if c.isalnum() or c in " -_.\n"] + list("abcxyz \n") + list(WIDE[:R.randrange(len(WIDE))])
    return "".join(R.choice(alpha) for _ in range(R.randrange(11)))


# ---- the port on Pystachy's strs
#
# A Pystachy str holds UTF-8, and the port reads it byte by byte (_UTF8 is true there): every other
# pattern runs that way here, on CPython strs that hold one byte per character (b()), with what
# Pystachy's chr() of a code point and repr() of a str give in the place of CPython's. What the
# port gives goes back to code points (u(), and a position as the number of characters before it)
# to be compared with CPython's re: a position inside a character's bytes fails there.

def b(s):
    # the Pystachy str of a CPython str: its UTF-8 bytes, one character per byte
    return s.encode("utf-8").decode("latin-1")


def u(s):
    # the CPython str of a Pystachy str
    return s.encode("latin-1").decode("utf-8")


CP_CHR = port._chr


def utf8_chr(c):
    return b(chr(c))


def utf8_repr(x):
    # Pystachy's repr() of a str escapes what CPython's escapes, character by character
    return b(repr(u(x))) if isinstance(x, str) else repr(x)


def utf8_ord(c):
    # Pystachy's ord() of a character's bytes is its code point (of a single byte, the byte)
    return ord(u(c)) if len(c) > 1 else ord(c)


def utf8(on):
    port._UTF8 = on
    port._chr = utf8_chr if on else CP_CHR
    if on:
        port.repr = utf8_repr
        port.ord = utf8_ord
    else:
        port.__dict__.pop("repr", None)
        port.__dict__.pop("ord", None)


def mine(x):
    # a str the port gave, or a list or tuple of them, as CPython's strs
    if not port._UTF8:
        return x
    if isinstance(x, str):
        return u(x)
    if isinstance(x, (list, tuple)):
        return type(x)(mine(y) for y in x)
    return x


def chars(s, i):
    # the port's position i in its str s as a number of characters
    return len(u(s[:i])) if port._UTF8 and i > 0 else i


def where(s, i):
    # the port's position for CPython's position i in s (beyond the end or below 0, as far)
    if not port._UTF8 or i <= 0:
        return i
    if i > len(s):
        return len(b(s)) + i - len(s)
    return len(b(s[:i]))


# ---- the comparisons

def outcome(f, conv=lambda r: r, own=False):
    # f()'s result (conv turns the port's into CPython's terms), or its exception: its type,
    # message and position, and its str() where positions are code points in both
    try:
        return ("ok", conv(f()))
    except Exception as e:  # the port raises CPython's exception types and messages
        msg = getattr(e, "msg", None)
        msg = str(e) if msg is None else msg
        pos = getattr(e, "pos", None)
        if own and port._UTF8:
            msg = u(msg)
            pos = None if pos is None else chars(e.pattern, pos)
        return (type(e).__name__, msg, pos, None if port._UTF8 else str(e))


def summary(m):
    # a match: its span, its groups' spans, lastindex and lastgroup, pos and endpos, positions as
    # code points
    if m is None:
        return None
    s = m.string
    if isinstance(m, re.Match):
        return (m.span(), tuple(m.span(i) for i in range(1, m.re.groups + 1)), m.lastindex, m.lastgroup, m.pos, m.endpos)
    span = (chars(s, m.start()), chars(s, m.end()))
    groups = tuple((chars(s, m.start(i)), chars(s, m.end(i))) for i in range(1, m.re.groups + 1))
    return (span, groups, m.lastindex, mine(m.lastgroup), chars(s, m.pos), chars(s, m.endpos))


def same(name, got, want, args):
    global fails, cases
    cases += 1
    if got != want:
        fails += 1
        if fails <= 20:
            print(f"FAIL {name}{args!r}{' (UTF-8)' if port._UTF8 else ''}: lib/re {got!r}, CPython {want!r}")


def finds(p, s):
    # the port's findall(); of 2 groups or more, NotImplementedError (a documented deviation), so
    # finditer() and m.group(i) instead, with '' for None as findall() has
    r = outcome(lambda: p.findall(s), mine, True)
    if p.groups >= 2 and r[0] == "NotImplementedError":
        return outcome(lambda: [tuple("" if g is None else g for g in (m.group(i) for i in range(1, p.groups + 1))) for m in p.finditer(s)], mine, True)
    return r


def splits(p, s, n, own):
    # split(), where CPython's list holds None as NotImplementedError: the port's list[str] cannot
    # hold it (a documented deviation)
    r = outcome(lambda: p.split(s, n), mine if own else lambda r: r, own)
    if not own and r[0] == "ok" and None in r[1] or own and r[0] == "NotImplementedError":
        return ("NotImplementedError",)
    return r


def repl(m):
    # a function as the replacement: the match and its start (in code points)
    i = m.start() if isinstance(m, re.Match) else chars(m.string, m.start())
    return "<%s|%d>" % (m.group(0), i)


def check(pat, fl, strings=()):
    # pat compiled with flags fl by both, then matched against the given strings and STRINGS random ones
    global patterns, valid
    patterns += 1
    enc = b if port._UTF8 else lambda s: s
    args = (pat, int(fl))
    want = outcome(lambda: re.compile(pat, fl))
    got = outcome(lambda: port.compile(enc(pat), fl), own=True)
    if want[0] != "ok" or got[0] != "ok":
        same("compile", got, want, args)
        return
    valid += 1
    cp, pp = want[1], got[1]
    code = [int(c) for c in re._compiler._code(re._parser.parse(pat, fl), fl)]
    same("code", (pp._code, pp.groups, {mine(k): v for k, v in pp.groupindex.items()}, int(pp.flags), mine(repr(pp))),
         (code, cp.groups, dict(cp.groupindex), int(cp.flags), repr(cp)), args)
    if pp._code != code:
        return
    temps = ["-", r"<\g<0>>", r"\g<0>\g<0>", "é"] + [r"[\%d]" % i for i in range(1, min(cp.groups, 2) + 1)]
    temps += [r"\g<%s>" % name for name in sorted(cp.groupindex)[:1]]
    for s in list(strings) + [text(pat) for _ in range(STRINGS)]:
        ps = enc(s)
        a = args + (s,)
        for name in ["search", "match", "fullmatch"]:
            same(name, outcome(lambda: summary(getattr(pp, name)(ps)), own=True), outcome(lambda: summary(getattr(cp, name)(s))), a)
        pos, end = R.randrange(-2, len(s) + 3), R.choice([len(s), R.randrange(-1, len(s) + 3), 1 << 62])
        ppos, pend = where(s, pos), where(s, end)
        for name in ["search", "match", "fullmatch"]:
            same(name, outcome(lambda: summary(getattr(pp, name)(ps, ppos, pend)), own=True),
                 outcome(lambda: summary(getattr(cp, name)(s, pos, end))), a + (pos, end))
        same("findall", finds(pp, ps), outcome(lambda: cp.findall(s)), a)
        same("finditer", outcome(lambda: [summary(m) for m in pp.finditer(ps, ppos, pend)], own=True),
             outcome(lambda: [summary(m) for m in cp.finditer(s, pos, end)]), a + (pos, end))
        n = R.choice([0, 0, 1, 2, -1])
        same("split", splits(pp, ps, n, True), splits(cp, s, n, False), a + (n,))
        t = R.choice(temps)
        n = R.choice([0, 0, 1, 2])
        same("subn", outcome(lambda: pp.subn(enc(t), ps, n), mine, True), outcome(lambda: cp.subn(t, s, n)), a + (t, n))
        same("subn", outcome(lambda: pp.subn(repl, ps), mine, True), outcome(lambda: cp.subn(repl, s)), a + ("repl",))
        m1, m2 = pp.search(ps), cp.search(s)
        if m1 is not None and m2 is not None:
            same("expand", outcome(lambda: m1.expand(enc(t)), mine, True), outcome(lambda: m2.expand(t)), a + (t,))
            if not port._UTF8:
                same("repr", repr(m1), repr(m2), a)


def check_upstream(how, pat, fl, s):
    # one of Lib/test/test_re.py's cases: the code pat compiles to (and the pattern's repr), and the
    # match of how ("match", "search" or "fullmatch"; "repr" for none) on s
    enc = b if port._UTF8 else lambda x: x
    args = (how, pat if len(pat) < 60 else pat[:60] + "...", int(fl), len(s))
    want = outcome(lambda: re.compile(pat, fl))
    got = outcome(lambda: port.compile(enc(pat), fl), own=True)
    if want[0] != "ok" or got[0] != "ok":
        same("compile", got, want, args)
        return
    cp, pp = want[1], got[1]
    code = [int(c) for c in re._compiler._code(re._parser.parse(pat, fl), fl)]
    same("code", (pp._code, mine(repr(pp))), (code, repr(cp)), args)
    if how != "repr":
        same(how, outcome(lambda: summary(getattr(pp, how)(enc(s))), own=True), outcome(lambda: summary(getattr(cp, how)(s))), args)


# Lib/test/test_re.py's cases that tests/upstream_re_*.py run on smaller inputs or leave out, as too
# costly with a collection at every allocation (make verify's gc-stress), here at upstream's sizes
BIG = '|'.join(['%d' % x for x in range(10000)])
UPSTREAM = [
    # test_ignore_case_range: ranges of 65,000 code points, which the port's compiler case-folds one by one
    ("match", r'[N-\uffff]', re.I | re.A, 'A'), ("match", r'[n-\uffff]', re.I | re.A, 'Z'),
    ("match", r'[N-\U00010000]', re.I | re.A, 'A'), ("match", r'[n-\U00010000]', re.I | re.A, 'Z'),
    # test_big_codesize: 10,000 alternatives, 107,792 words of code
    ("match", BIG, 0, '1000'), ("match", BIG, 0, '9999'),
    # test_look_behind_overflow: a lookbehind 2**21 characters wide
    ("search", r"(?<=((.{128}){128}){128})", 0, "x" * 2_500_000), ("search", r"(?<!((.{128}){128}){128})", 0, "x" * 2_500_000),
    # test_stack_overflow
    ("match", '(x)*', 0, 50000 * 'x'), ("match", '(x)*y', 0, 50000 * 'x' + 'y'), ("match", '(x)*?y', 0, 50000 * 'x' + 'y'),
    # test_bug_418626
    ("match", '.*?c', 0, 10000 * 'ab' + 'cd'), ("match", '.*?cd', 0, 5000 * 'ab' + 'c' + 5000 * 'ab' + 'cde'),
    ("match", '.*?cd', 0, 20000 * 'abc' + 'de'), ("search", '(a|b)*?c', 0, 10000 * 'ab' + 'cd'),
    # test_search_anchor_at_beginning (on 10**6 characters, not 10**7)
    ("search", r'\Ay', 0, 'x' * 10**6), ("search", r'^y', 0, 'x' * 10**6),
    # PatternReprTests.test_long_pattern
    ("repr", 'Very %spattern' % ('long ' * 1000), 0, ''), ("repr", 'Very %spattern' % ('long ' * 1000), re.I, ''),
]
for how, p, f, s in UPSTREAM:
    # (the 2,500,000 ASCII characters of the lookbehind's string only as code points: as UTF-8 the
    # port reads them alike, in another 3 seconds)
    for on in [False, True] if len(s) < 10**6 + 1 else [False]:
        utf8(on)
        check_upstream(how, p, f, s)
for k in range(N):
    p, f = pattern(), flags()
    utf8(k % 2 == 1)
    check(p, f)
print(f"{len(UPSTREAM)} upstream cases and {patterns} patterns ({valid} valid): {cases} cases, {fails} failed")
sys.exit(1 if fails else 0)
