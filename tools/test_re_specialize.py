"""Tests of tools/re_specialize.py: the matchers it generates must match as CPython's re does.

lib/re runs on CPython as a package of its own (as in tools/re_fuzz.py), here importing a module of
matchers generated for random patterns: every construct the generator writes (literals, classes,
categories and case-insensitive forms, anchors and boundaries, marks, alternatives, greedy, lazy and
possessive repeats of characters and of groups, lookahead and lookbehind, atomic groups and
backreferences), with flags. Each pattern then runs on random strings, compared with CPython's re:
the spans, groups, lastindex and lastgroup of search(), match() and fullmatch() (also with pos and
endpos), findall(), finditer(), split() and subn(). Strings of ASCII run the generated matcher, which
lib/re reads in place; others are decoded, and the matcher declines them. Each pattern also runs on
random subjects of all 256 byte values read in place (as Pystachy reads a file whose bytes are not
UTF-8), against CPython's re on the same code points (their Latin-1 decoding).

usage: python3 -m unittest discover -s tools -p test_re_specialize.py
       python3 tools/re_specialize.py check [N] [SEED]   (N random patterns, more output)
"""
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re_specialize  # noqa: E402

ROOT = re_specialize.ROOT
TEST = os.path.join(ROOT, "tests", "re_specialize.py")
CHECKED_IN = os.path.join(ROOT, "tests", "re_specialize_matchers", "_pystachy_re_specialized.py")
LIMIT = "re.findall() of a pattern with"  # (lib/re's deviations: NotImplementedError, lib/README.md)


# ---- random patterns


class Patterns:
    """Random patterns of the constructs the generator writes, and some it does not."""

    def __init__(self, rng):
        self.r = rng

    def pattern(self):
        r = self.r
        self.groups = 0  # groups opened
        self.closed = []  # their numbers, once closed (a backreference needs one)
        p = self.alternation(0)
        lead = r.choice(["", "", "", "(?i)", "(?s)", "(?m)", "(?a)", "(?i)(?m)"])
        return lead + p, r.choice([0, 0, 0, re.I, re.M, re.S, re.A, re.I | re.S])

    def alternation(self, depth):
        n = 1 if depth > 2 or self.r.random() < 0.7 else self.r.randint(2, 3)
        return "|".join(self.sequence(depth) for _ in range(n))

    def sequence(self, depth):
        return "".join(self.item(depth) for _ in range(self.r.randint(1, 4 if depth == 0 else 3)))

    def item(self, depth):
        atom, nested = self.atom(depth)
        r = self.r
        if r.random() < 0.35 and not atom.startswith(("(?=", "(?!", "(?<", "^", "$", "\\A", "\\Z", "\\b", "\\B")):
            # (a repeat of something that repeats is bounded: unbounded, it backtracks exponentially)
            q = r.choice(["{0,2}", "{1,3}", "?", "{2}"] if nested else
                         ["*", "+", "?", "{2}", "{1,3}", "{,2}", "{2,}", "*", "+"])
            atom += q + r.choice(["", "", "", "?", "+"])
        return atom

    def atom(self, depth):
        r = self.r
        k = r.randrange(22)
        if k < 6:
            return r.choice(["a", "b", "c", "x", "-", "\\.", " ", "A", "\\n", "1", "\u00e9"]), False
        if k == 6:
            return ".", False
        if k == 7:
            return r.choice(["[abc]", "[^ab]", "[a-c]", "[\\d_]", "[^\\s]", "[xA-C]", "[^a-z]", "[.\\-]",
                             "[\u00e0-\u00ff]", "[^\u00e9]"]), False
        if k == 8:
            return r.choice(["\\d", "\\w", "\\s", "\\D", "\\W", "\\S"]), False
        if k == 9:
            return r.choice(["^", "$", "\\A", "\\Z", "\\b", "\\B"]), False
        if depth >= 3:
            return r.choice(["a", "b", "x"]), False
        if k in (10, 11):
            self.groups += 1
            g = self.groups
            inner = self.alternation(depth + 1)
            self.closed.append(g)
            name = "(?P<g%d>" % g if r.random() < 0.2 else "("
            return name + inner + ")", self.repeats(inner)
        if k in (12, 13):
            inner = self.alternation(depth + 1)
            return "(?:" + inner + ")", self.repeats(inner)
        if k == 14:
            return r.choice(["(?=", "(?!"]) + self.alternation(depth + 1) + ")", False
        if k == 15:
            # lookbehind: of a fixed width
            body = "".join(r.choice(["a", "b", "x", "\\d", ".", "[ab]"]) for _ in range(r.randint(1, 2)))
            if r.random() < 0.3:
                body = body + "|" + "".join(r.choice(["c", "\\w", "y"]) for _ in range(len(body.replace("\\", ""))))
            return r.choice(["(?<=", "(?<!"]) + body + ")", False
        if k == 16:
            inner = self.alternation(depth + 1)
            return "(?>" + inner + ")", self.repeats(inner)
        if k == 17 and self.closed:
            return "\\%d" % r.choice(self.closed), True
        if k == 18:
            return "(?i:" + self.sequence(depth + 1) + ")", True
        return r.choice(["ab", "x", "a", "b"]), False

    def repeats(self, inner):
        return any(c in inner for c in "*+?{|") or "\\" in inner

    def subject(self, pattern, n):
        r = self.r
        letters = [c for c in pattern if c.isalnum() or c in "-_. \n"] or ["a"]
        alphabet = letters + list("abcxAB1 -.\n_")
        return "".join(r.choice(alphabet) for _ in range(r.randint(0, n)))


# Patterns whose groups the interpreter's marks decide in ways a random pattern seldom shows: marks
# restored inside repeats and alternatives (and not past lastmark), gaps cleared, stale groups kept,
# empty iterations, lookaround groups, backreferences, anchors, flags (with their subjects)
CASES = [
    (r"(a)x|.(c)", 0, ["ac", "axc", "c"]),
    (r"(?:(a)|b)*", 0, ["ab", "ba", "aab", ""]),
    (r"(?:(a?))*", 0, ["a", "aa", "b"]),
    (r"((a)|b)+", 0, ["ab", "ba", "bab"]),
    (r"(a*)*", 0, ["aa", "", "ab"]),
    (r"(a|b)*?c", 0, ["abc", "c", "abab"]),
    (r"(?=(a))", 0, ["a", "ba"]),
    (r"(?!(a)b)\w", 0, ["ac", "ab", "xb"]),
    (r"(?:a|)*", 0, ["aa", ""]),
    (r"(a?)+b", 0, ["ab", "b", "aab"]),
    (r"(?:x(a)|x(b))c", 0, ["xbc", "xac", "xc"]),
    (r"(?>(a)|ab)c", 0, ["abc", "ac"]),
    (r"((?:a|)*)b", 0, ["aab", "b"]),
    (r"(a)(b)?(c)?d", 0, ["abd", "acd", "ad", "abcd"]),
    (r"(?P<x>a)(?P=x)", 0, ["aa", "ab"]),
    (r"(a)\1|b\1?", 0, ["aa", "ab", "b"]),
    (r"(a)(?i:\1)", 0, ["aA", "aa", "ab"]),
    (r"(?i)(a)\1", 0, ["aA", "Aa", "ab"]),
    (r"(?:ab)++c", 0, ["ababc", "abc", "abab"]),
    (r"a++a", 0, ["aaa"]),
    (r"(?:a|ab)++c", 0, ["abc", "ac", "aac"]),
    (r"x*", 0, ["", "axxb", "xx"]),
    (r"|a", 0, ["a", "ba"]),
    (r"\b", 0, ["ab c", "", " "]),
    (r"\B", 0, ["ab c", "", " "]),
    (r"^a|b$", re.M, ["a\nb", "b\na\n", "xb\n"]),
    (r"$", 0, ["a\n", "a", "\n\n"]),
    (r"a.c", re.S, ["a\nc", "abc"]),
    (r"(?<=a)b|(?<!a)c", 0, ["abc", "cb", "ac"]),
    (r"(?<=(a))b", 0, ["ab", "b"]),
    (r"(?<!(a))b", 0, ["ab", "cb"]),
    (r"(?i)[^\u00e9]+", 0, ["abc\u00c9", "xy"]),
    (r"(?i)\u00e9+", 0, ["\u00c9\u00e9", "e"]),
    (r"\w+", re.A, ["ab_1 c", "\u00e9t\u00e9"]),
    (r"[\u00e0-\u00ff]+|\d{2,}?", 0, ["\u00e9\u00e8 123", "12"]),
    (r"(a{2,3}?)(a*)", 0, ["aaaaa", "aa", "a"]),
    (r"(?:(a)|(b)|(c))+", 0, ["abc", "cba", "aa"]),
    (r"((a)|b)*?(?(2)x|y)", 0, ["abx", "by"]),  # (not generated: GROUPREF_EXISTS)
]


# ---- comparisons


def spans(m, groups):
    if m is None:
        return None
    return ([m.span(i) for i in range(groups + 1)], m.lastindex, m.lastgroup)


def outcome(f, arg):
    try:
        return ("ok", f(arg))
    except NotImplementedError as e:
        return ("limit", str(e))
    except Exception as e:
        return ("raise", type(e).__name__, str(e))


def compare(port, cp, pattern, flags, s, problems):
    # the public API of lib/re's Pattern against CPython's, on the str s
    want = re.compile(pattern, flags)
    g = cp.groups
    calls = [("search", lambda p: spans(p.search(s), g)),
             ("match", lambda p: spans(p.match(s), g)),
             ("fullmatch", lambda p: spans(p.fullmatch(s), g)),
             ("search(pos)", lambda p: spans(p.search(s, 1), g)),
             ("match(pos, endpos)", lambda p: spans(p.match(s, 1, len(s) - 1), g)),
             ("finditer", lambda p: [spans(m, g) for m in p.finditer(s)]),
             ("findall", lambda p: p.findall(s)),
             ("split", lambda p: p.split(s)),
             ("subn", lambda p: p.subn("<\\g<0>>", s)),
             ("sub(fn)", lambda p: p.sub(lambda m: str(m.span()), s, 3))]
    for name, f in calls:
        got = outcome(f, cp)
        exp = outcome(f, want)
        if got[0] == "limit" and (LIMIT in got[1] or "did not take part" in got[1]):
            continue
        if got != exp:
            problems.append("%s %r flags %d on %r: lib/re %r, CPython %r" % (name, pattern, flags, s, got, exp))


def compare_bytes(port, cp, pattern, flags, data, problems):
    # the matcher on a subject read in place, of any byte values, against CPython's re on their code
    # points (a Pystachy str whose bytes are not UTF-8 reads them as the code points they are)
    sre = sys.modules[port.__name__ + "._sre"]
    text = data.decode("latin-1")
    want = re.compile(pattern, flags)
    for pos, endpos, kind in ((0, len(data), "search"), (0, len(data), "match"), (0, len(data), "fullmatch"),
                              (min(2, len(data)), len(data), "search")):
        st = sre.State(data, pos, endpos, cp.groups, port._NO_OFFS, cp._charset_offsets, cp._charset_ascii,
                       cp._prefilter)
        st.fast = cp._fast
        if kind == "search":
            status = sre.sre_search(st, cp._code)
        else:
            st.match_all = kind == "fullmatch"
            status = cp._run_match(st)
        got = spans(cp._new_match(text, st), cp.groups) if status else None
        m = (want.search(text, pos, endpos) if kind == "search" else want.match(text, pos, endpos)
             if kind == "match" else want.fullmatch(text, pos, endpos))
        exp = spans(m, cp.groups)
        if got != exp:
            problems.append("%s %r flags %d on bytes %r: lib/re %r, CPython %r" % (kind, pattern, flags, data, got, exp))


def fuzz(n, seed, verbose=False):
    """Generate matchers for n random patterns (from seed) and compare; 0 if all agree."""
    rng = random.Random(seed)
    gen = Patterns(rng)
    patterns = []
    subjects = {}
    for p, f, cases in CASES:
        key = (p, re.compile(p, f).flags)
        patterns.append(key)
        subjects[key] = [c.encode().decode("unicode_escape") if "\\" in c else c for c in cases]
    for _ in range(n):
        p, f = gen.pattern()
        try:
            key = (p, re.compile(p, f).flags)
        except (re.error, OverflowError, RecursionError):
            continue
        if key not in subjects:
            patterns.append(key)
            subjects[key] = []
    with tempfile.TemporaryDirectory(prefix="re-specialize-") as tmp:
        out = os.path.join(tmp, "_pystachy_re_specialized.py")
        module = re_specialize.generate([], patterns, 1, out)
        port = re_specialize.load_port(out)
        matchers = sys.modules["_pystachy_re_specialized"]
        used = [0, 0]  # matcher calls that answered, and that declined

        def counted(f):
            def call(i, state, *toplevel):
                r = f(i, state, *toplevel)
                used[0 if r >= 0 else 1] += 1
                return r
            return call
        matchers.match = counted(matchers.match)
        matchers.attempt = counted(matchers.attempt)
        problems = []
        specialized = 0
        for p, f in patterns:
            try:
                cp = port.compile(p, f)
            except Exception as e:
                problems.append("compile %r flags %d: lib/re raises %r, CPython compiles it" % (p, f, e))
                continue
            if cp._fast >= 0:
                specialized += 1
            for text in subjects[(p, f)]:
                compare(port, cp, p, f, text, problems)
                if text.isascii():
                    compare_bytes(port, cp, p, f, text.encode(), problems)
            for _ in range(12):
                compare(port, cp, p, f, gen.subject(p, 14), problems)
            compare(port, cp, p, f, "\u00e9" + gen.subject(p, 8), problems)
            for _ in range(4):
                data = bytes(rng.choice([97, 98, 120, 32, 10, 49, 65, 0xe9, 0xc9, 0xaa, 0xb5, 0xa0, 0x85, 0xff, 95])
                             for _ in range(rng.randint(0, 10)))
                compare_bytes(port, cp, p, f, data, problems)
            if len(problems) > 20:
                break
    if verbose:
        for line in problems[:20]:
            print("FAIL " + line)
        print("%d patterns (%d generated, %d specialized), matcher calls %d answered, %d declined: %d failed"
              % (len(patterns), len(module.patterns), specialized, used[0], used[1], len(problems)))
    return (problems, len(patterns), len(module.patterns), specialized, used)


class TestGenerated(unittest.TestCase):
    def test_fuzz(self):
        problems, total, generated, specialized, used = fuzz(300, 1)
        self.assertEqual(problems, [])
        # (most random patterns are generated; their subjects read in place run the matchers)
        self.assertGreater(generated, total * 3 // 4)
        self.assertEqual(generated, specialized)
        self.assertGreater(used[0], 20000)

    def test_deep_repeat_declines(self):
        # a match that nests more group repeats than DEPTH is left to the interpreter, from the start
        with tempfile.TemporaryDirectory(prefix="re-specialize-") as tmp:
            out = os.path.join(tmp, "_pystachy_re_specialized.py")
            re_specialize.generate([], [("(?:ab)*c", 0), ("x(?:ab)*?c", 0)], 1, out)
            port = re_specialize.load_port(out)
            for p in ["(?:ab)*c", "x(?:ab)*?c"]:
                for k in [10, re_specialize.DEPTH + 10]:
                    s = "x" + "ab" * k + "c"
                    self.assertEqual(port.search(p, s).span(), re.search(p, s).span())

    def test_empty_iterations_stop(self):
        # an iteration of a group repeat that matched nothing ends it (_sre's last_ptr), here as there:
        # these short matches are answered, not left to the interpreter by DEPTH
        with tempfile.TemporaryDirectory(prefix="re-specialize-") as tmp:
            out = os.path.join(tmp, "_pystachy_re_specialized.py")
            pats = ["(?:a?)*b", "(?:(a?))*", "(?:a|)*?b", "(?:a?)++b"]
            re_specialize.generate([], [(p, 0) for p in pats], 1, out)
            port = re_specialize.load_port(out)
            matchers = sys.modules["_pystachy_re_specialized"]
            declined = []
            attempt = matchers.attempt

            def counted(i, state, toplevel):
                r = attempt(i, state, toplevel)
                if r < 0:
                    declined.append(i)
                return r
            matchers.attempt = counted
            for p in pats:
                groups = re.compile(p).groups
                for s in ["aab", "b", "ab" * 5]:
                    self.assertEqual(spans(port.search(p, s), groups), spans(re.search(p, s), groups))
            self.assertEqual(declined, [])

    def test_not_generated(self):
        with tempfile.TemporaryDirectory(prefix="re-specialize-") as tmp:
            out = os.path.join(tmp, "_pystachy_re_specialized.py")
            module = re_specialize.generate([], [("(a)?(?(1)b|c)", 0), ("[", 0)], 1, out)
            self.assertEqual(module.patterns, [])
            reasons = [reason for _, _, reason in module.skipped]
            self.assertEqual(reasons[0], "GROUPREF_EXISTS")
            self.assertIn("unterminated character set", reasons[1])
            port = re_specialize.load_port(out)
            self.assertEqual(port.compile("(a)?(?(1)b|c)")._fast, -1)

    def test_lookup_checks_code(self):
        # a matcher made from other code than the pattern compiles to is not used
        with tempfile.TemporaryDirectory(prefix="re-specialize-") as tmp:
            out = os.path.join(tmp, "_pystachy_re_specialized.py")
            re_specialize.generate([], [("a+b", 0)], 1, out)
            port = re_specialize.load_port(out)
            matchers = sys.modules["_pystachy_re_specialized"]
            code = port.compile("a+b")._code
            self.assertEqual(matchers.lookup("a+b", re.U, code), 0)
            self.assertEqual(matchers.lookup("a+b", re.U, code[:-1] + [0]), -1)
            self.assertEqual(matchers.lookup("a+b", re.U | re.I, code), -1)
            self.assertEqual(matchers.lookup("a+c", re.U, code), -1)

    def test_lib_has_none(self):
        port = re_specialize.load_port()
        self.assertEqual(port.compile("a+b")._fast, -1)

    def test_record(self):
        with tempfile.TemporaryDirectory(prefix="re-specialize-") as tmp:
            prog = os.path.join(tmp, "prog.py")
            with open(prog, "w") as f:
                f.write("import re\nimport sys\nP = re.compile(r'\\d+')\nfor _ in range(int(sys.argv[1])):\n"
                        "    P.search('a1')\nre.findall('b+', 'abb')\nre.compile('unused')\n")
            out = os.path.join(tmp, "profile.json")
            subprocess.run([sys.executable, os.path.join(ROOT, "tools", "re_specialize.py"), "record", "-o", out,
                            prog, "7"], check=True)
            with open(out) as f:
                profile = json.load(f)
            calls = {(e["pattern"], e["flags"]): e["calls"] for e in profile["patterns"]}
            self.assertEqual(calls, {("\\d+", re.U): 7, ("b+", re.U): 1})

    def test_checked_in(self):
        # tests/re_specialize_matchers/ holds the matchers of tests/re_specialize.py's patterns, as the
        # tool writes them from a profile of the test under CPython
        with tempfile.TemporaryDirectory(prefix="re-specialize-") as tmp:
            profile = os.path.join(tmp, "re_specialize.json")
            out = os.path.join(tmp, "_pystachy_re_specialized.py")
            tool = os.path.join(ROOT, "tools", "re_specialize.py")
            subprocess.run([sys.executable, tool, "record", "-o", profile, TEST], check=True, cwd=ROOT,
                           stdout=subprocess.DEVNULL)
            subprocess.run([sys.executable, tool, "generate", "-o", out, profile], check=True, cwd=ROOT,
                           stdout=subprocess.DEVNULL)
            with open(out) as f, open(CHECKED_IN) as g:
                self.assertEqual(f.read(), g.read(), "regenerate %s (see its test)" % CHECKED_IN)


if __name__ == "__main__":
    unittest.main()
