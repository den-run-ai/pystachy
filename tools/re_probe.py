"""re_probe: what lib/re does for textwrap's regular expressions, counted, and optionally timed.

lib/re is ordinary Python, so CPython runs it as a package of its own (pys_re, as in
tools/re_fuzz.py). On re_bench.inputs(20), 20 paragraphs and 20 blocks made as tools/re_bench.py
makes its inputs (the paragraphs are the first 20 it times; the blocks, drawn after them, are not
the ones it times), it runs each operation of textwrap's patterns, checks its result against
CPython's re, and counts the matcher's entries (calls of _sre.sre_match: a search's attempts, and
sre_count()'s nested ones) and the contexts it makes (_sre.Ctx objects). The counts are
deterministic: the run fails if one is above its limit, so a change to lib/re that makes the matcher
do more fails here, and one that makes it do less lowers the limits.

The charset compiler also checks full BMP and non-BMP case-insensitive ranges against CPython's
code and matches. Its bit-setting calls may only receive existing case-fix lists, never temporary
singleton/empty lists per code point; this deterministic guard needs no timing threshold.
Repeated case-insensitive classes must also count their run without entering the matcher for
each character, with the same one entry and context as a case-sensitive class. Class runs and the
scans of a search for a class make no class call per character (_charset() or charset()) once
the Pattern's table for the class is built, for ASCII text and for classes whose members from
U+0080 are one range, none or all. An alternative's nested match is entered only where all its
leading literals and classes match, and a greedy repeat whose tail begins with group marks and a
literal enters the tail only where that literal is: the contexts the matcher enters are counted.
A search whose pattern begins with alternatives that all begin with literals and classes, or
whose matches all hold literals at a bounded offset from their start, enters the matcher only
where those can be: its entries are counted. Warm case-insensitive and Unicode classes answer
repeated non-ASCII code points from memos: no charset() evaluation, no case-mapping search. The
bit-parallel filter of such alternatives gives no bits, untested, to a non-ASCII character that
none of their leading items may match, and answers the others from its memo once warm.

The time of a call of lib/re under CPython says little about compiled code: --time PYSTACHY builds
tools/re_bench.py with that compiler and prints each operation's time per call, compiled and under
CPython's own re, for information only.

usage: python3 tools/re_probe.py [--time PYSTACHY]   (make re-probe; a step of make verify)
"""
import builtins
import importlib.util
import os
import random
import re
import re._compiler
import re._parser
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import re_bench  # noqa: E402  (the patterns and the inputs)

# lib/re's private primitives, which Pystachy compiles for re alone: a str's UTF-8 size, and the
# bytes of a str whose every character is a byte (an ASCII str, on CPython)
builtins.__pys_text_size = lambda s: len(s.encode("utf-8", "surrogatepass"))
builtins.__pys_text_bytes = lambda s: s.encode("latin-1")
_spec = importlib.util.spec_from_file_location("pys_re", os.path.join(ROOT, "lib", "re", "__init__.py"),
                                               submodule_search_locations=[os.path.join(ROOT, "lib", "re")])
port = importlib.util.module_from_spec(_spec)
sys.modules["pys_re"] = port
_spec.loader.exec_module(port)
sre = sys.modules["pys_re._sre"]
counts = {"entries": 0, "contexts": 0, "entered": 0}
_sre_match = sre.sre_match
_Ctx = sre.Ctx


def _counted_match(state, code, start, toplevel):
    counts["entries"] += 1
    return _sre_match(state, code, start, toplevel)


class _CountedCtx(_Ctx):
    # contexts: made; entered: made or reused (each match and each nested match it waits for)
    def __init__(self, *args):
        counts["contexts"] += 1
        counts["entered"] += 1
        super().__init__(*args)

    def reuse(self, *args):
        counts["entered"] += 1
        super().reuse(*args)


sre.sre_match = _counted_match
sre.Ctx = _CountedCtx

# name, pattern, flags, what it does to what, and the limits of its matcher entries and contexts
# over the 20 inputs
OPERATIONS = [
    ("wordsep_re.split", re_bench.WORDSEP, re.VERBOSE, "split", 3414, 140),
    ("wordsep_simple_re.split", re_bench.WORDSEP_SIMPLE, 0, "split", 1580, 40),
    ("whitespace_only_re.sub", re_bench.WHITESPACE_ONLY, re.MULTILINE, "sub", 320, 40),
    ("leading_whitespace_re.findall", re_bench.LEADING_WHITESPACE, re.MULTILINE, "findall", 320, 40),
    ("margin.sub", r"(?m)^    ", 0, "sub", 298, 20),
]


def run(rx, what: str, text: str):
    if what == "split":
        return rx.split(text)
    if what == "sub":
        return rx.sub("", text)
    return rx.findall(text)


def check_charset_allocations() -> int:
    # The shared empty result and Unicode case-fix table stay alive throughout this check.
    # Counting unowned list arguments catches both singleton and empty per-code-point lists,
    # including a regression that changes _Case.fixes() back to returning a fresh empty list.
    empty = port._Case(port.A | port.I).fixes(0)
    owned = {id(empty)} | {id(fixes) for fixes in port._fixes().values()}
    calls = fresh = failed = 0
    original = port._setbits

    def counted(charmap, ks):
        nonlocal calls, fresh
        calls += 1
        fresh += id(ks) not in owned
        return original(charmap, ks)

    patterns = [r'[N-\uffff]', r'[n-\uffff]', r'[N-\U00010000]', r'[n-\U00010000]',
                r'[N-\U0010ffff]', r'[^N-\uffff]', r'[9-\xff]', r'[9-\u0100]',
                r'[\xb5-\xb6]', r'[\U00010400-\U00010427]', r'[19\u0100]']
    subjects = ['\x00', '9', '@', 'A', 'M', 'N', 'Z', '[', '`', 'a', 'm', 'n', 'z',
                '\xff', '\u0100', '\u0101', '\xb5', '\u039c', '\u03bc', '\u017f',
                '\u212a', '\uffff', '\U00010000', '\U00010001', '\U00010400',
                '\U00010428', '\U0010ffff']
    port._setbits = counted
    try:
        for flags in [0, re.I, re.I | re.A]:
            for pattern in patterns:
                port.purge()
                mine = port.compile(pattern, flags)
                theirs = re.compile(pattern, flags)
                code = [int(c) for c in re._compiler._code(re._parser.parse(pattern, flags), flags)]
                if mine._code != code:
                    print(f'charset bytecode differs: {pattern!r}, {flags}')
                    failed += 1
                for subject in subjects:
                    got = mine.fullmatch(subject)
                    want = theirs.fullmatch(subject)
                    if (None if got is None else got.group()) != (None if want is None else want.group()):
                        print(f'charset match differs: {pattern!r}, {flags}, {subject!r}')
                        failed += 1
    finally:
        port._setbits = original
    if fresh:
        failed += 1
    print(f'charset bit lists: {fresh} temporary of {calls} calls (limit 0)')
    return failed


def check_ignorecase_repeats() -> int:
    # A full match with no tail needs only its outer context, regardless of the run's length.
    # A missing count fast path enters the full matcher once per character instead.
    failed = entries = contexts = 0
    for flags, text in [(re.I | re.A, "AbCd" * 250), (re.I, "AbCd" * 250),
                        (re.I, "aſİıK" * 200)]:
        for repeat in ["+", "{1000}", "{1000}?", "++"]:
            pattern = "[a-z]" + repeat
            mine = port.compile(pattern, flags)
            theirs = re.compile(pattern, flags)
            counts["entries"] = counts["contexts"] = 0
            got = mine.fullmatch(text)
            want = theirs.fullmatch(text)
            if (None if got is None else got.group()) != (None if want is None else want.group()):
                print(f'ignorecase repeat differs: {pattern!r}, {flags}')
                failed += 1
            e, c = counts["entries"], counts["contexts"]
            entries += e
            contexts += c
            if e > 1 or c > 1:
                print(f'ignorecase repeat: {pattern!r}, {flags}: {e} entries, {c} contexts (limit 1 each)')
                failed += 1
    print(f'ignorecase repeats: {entries} entries, {contexts} contexts (limit 12 each)')
    return failed


def check_ignorecase_searches() -> int:
    # A nonempty repeat can only match where its first literal or class matches. Sparse and
    # absent runs must not enter the matcher once for every rejected position.
    failed = entries = contexts = 0
    for flags in [re.I | re.A, re.I]:
        for item in ["[a-z]", "a"]:
            for repeat in ["+", "{1,3}?", "++"]:
                pattern = "(" + item + repeat + ")!"
                mine = port.compile(pattern, flags)
                theirs = re.compile(pattern, flags)
                for text, max_entries in [("0" * 1000, 0), ("0" * 1000 + "Aa!", 1)]:
                    counts["entries"] = counts["contexts"] = 0
                    got = mine.search(text)
                    want = theirs.search(text)
                    if (None if got is None else (got.span(), got.group(1))) != (None if want is None else (want.span(), want.group(1))):
                        print(f'ignorecase search differs: {pattern!r}, {flags}')
                        failed += 1
                    e, c = counts["entries"], counts["contexts"]
                    entries += e
                    contexts += c
                    if e > max_entries or c > 2 * max_entries:
                        print(f'ignorecase search: {pattern!r}, {flags}: {e} entries, {c} contexts (limit {max_entries}, {2 * max_entries})')
                        failed += 1
    print(f'ignorecase searches: {entries} entries, {contexts} contexts (limit 12, 24)')
    return failed


def check_repeat_prefixes() -> int:
    # These are the captured and noncaptured multi-character repeat heads from regex_effbot.
    # MARK instructions preserve captures but cannot make a mandatory first character optional.
    failed = entries = 0
    for pattern in [r"([a-z][a-z0-9]*,)+", r"(?:[a-z][a-z0-9]*,)+",
                    r"([a-z][a-z0-9]*,)+?", r"(?:([a-z])([0-9]),){1,3}",
                    r"(?i:([a-z][a-z0-9]*,)+)"]:
        mine = port.compile(pattern)
        theirs = re.compile(pattern)
        for text, max_entries in [("-" * 1000, 0), ("-" * 1000 + "a5,b7,c9,", 1)]:
            counts["entries"] = counts["contexts"] = 0
            got = mine.search(text)
            want = theirs.search(text)
            if (None if got is None else (got.span(), got.groups())) != (None if want is None else (want.span(), want.groups())):
                print(f'repeat prefix differs: {pattern!r}')
                failed += 1
            e = counts["entries"]
            entries += e
            if e > max_entries:
                print(f'repeat prefix: {pattern!r}: {e} entries (limit {max_entries})')
                failed += 1
    print(f'repeat prefixes: {entries} entries (limit 5)')
    return failed


def check_class_spans() -> int:
    # A class run (a repeat's count) or a class scan (a search's skip to its first character)
    # finds the set's table once. Then neither an ASCII character nor, in a set whose members
    # from U+0080 are one range, none or all, any other one needs a call: not of _charset() for
    # each character, nor of charset()'s bytecode evaluation once the table is built. (A match
    # that begins with a single class, not a repeat, tests its one character with _charset().)
    failed = calls = 0
    counted = {"_charset": 0, "charset": 0}
    original = (sre._charset, sre.charset)

    def counted_charset_ascii(state, code, i, ch):
        counted["_charset"] += 1
        return original[0](state, code, i, ch)

    def counted_charset(code, i, ch):
        counted["charset"] += 1
        return original[1](code, i, ch)

    cases = [
        (r"[A-Za-z_]+", "AbCdEf_" * 150 + "!"),
        (r"(?ai:[a-z_]+)", "AbCdEf_" * 150 + "!"),
        (r"(?i:[a-z_]+)", "AbCdEf_" * 150 + "!"),
        (r"[^#?]+", "éА\U0001f600a" * 250 + "#"),
        (r"[Ѐ-ӿ]+", "Ая" * 500 + "!"),
        (r"[^\U00010000-\U0010ffff]+", "aé￿" * 300 + "\U00010000"),
        (r"([#?é])", "-" * 1000 + "é"),
        (r"([^\x00-\x7f])", "-" * 1000 + "А"),
        (r"([a-z]+)!", "0" * 1000 + "ab!"),
        (r"(?i:([a-z]+))!", "0" * 1000 + "Ab!"),
        (r"(?i:(k+))!", "0" * 1000 + "kK!"),
    ]
    sre._charset = counted_charset_ascii
    sre.charset = counted_charset
    try:
        for pattern, text in cases:
            mine = port.compile(pattern)
            theirs = re.compile(pattern)
            mine.findall(text)  # (builds the tables)
            counted["_charset"] = counted["charset"] = 0
            got = mine.findall(text)
            if got != theirs.findall(text):
                print(f'class span differs: {pattern!r}')
                failed += 1
            n = counted["_charset"] + counted["charset"]
            calls += n
            if n > 1:
                print(f'class span: {pattern!r}: {counted["_charset"]} _charset() and {counted["charset"]} charset() calls (limit 1)')
                failed += 1
    finally:
        sre._charset, sre.charset = original
    print(f'class spans: {calls} class calls over {len(cases)} cases (limit 1 each)')
    return failed


def check_nested_matches() -> int:
    # An alternative's nested match begins only where its leading literals and classes all match,
    # and a greedy repeat whose tail begins with group marks then a literal enters the tail only
    # where that literal is: count the contexts the matcher enters, made or reused.
    failed = total = 0
    rng = random.Random(1)
    dna = "".join([rng.choice("acgt") for _ in range(3000)])
    dashes = "-" * 1000 + "Python" + "-" * 1000
    cases = [
        (r"[acgt](?:agggtaaa|tttaccct)", dna, 3000),
        (r"[acgt](?:[cgt]gggtaaa|tttaccc[acg])", dna, 3000),
        (r"[acgt](a[act]ggtaaa|tttacc[agt]t)", dna, 3000),
        (r".*(Python)", dashes, 2),
        (r".*((P)y)thon", dashes, 2),
        (r"(.*)(P)ython", dashes, 2),
    ]
    for pattern, text, limit in cases:
        mine = port.compile(pattern)
        theirs = re.compile(pattern)
        counts["entered"] = 0
        got = [(m.span(), m.groups()) for m in mine.finditer(text)] if text is dna else mine.search(text).groups()
        if got != ([(m.span(), m.groups()) for m in theirs.finditer(text)] if text is dna else theirs.search(text).groups()):
            print(f'nested matches differ: {pattern!r}')
            failed += 1
        n = counts["entered"]
        total += n
        if n > limit:
            print(f'nested matches: {pattern!r}: {n} contexts entered (limit {limit})')
            failed += 1
    print(f'nested matches: {total} contexts entered over {len(cases)} cases')
    return failed


def check_prefilters() -> int:
    # A search whose pattern begins with alternatives that all begin with literals and classes
    # enters the matcher only where one of them can begin; one whose matches all have literals at
    # a bounded offset from their start, only where those are found (as in regex_dna and
    # regex_v8). Count the matcher's entries over each search.
    failed = total = 0
    rng = random.Random(2)
    dna = "".join([rng.choice("acgt") for _ in range(3000)])
    words = " ".join(["".join([rng.choice("abcdefgh;") for _ in range(rng.randint(1, 9))]) for _ in range(300)])
    js = words[:1000] + '"\\/Qngr(1234)\\/"' + words[1000:]
    cases = [
        (r"agggtaaa|tttaccct", dna, 0),
        (r"[cgt]gggtaaa|tttaccc[acg]", dna, 0),
        (r"(a[act]ggtaaa|tttacc[agt]t)", dna, 1),
        (r'(^|[^\\])\"\\\/Qngr\((-?[0-9]+)\)\\\/\"', js, 1),
        (r"\s?;\s?", words, 250),
        (r"(?i)TNQP=([^;]*)", words[:500] + "tnqp=1;" + words[500:], 1),
        (r"\bdefg\b", words, 0),
    ]
    for pattern, text, limit in cases:
        mine = port.compile(pattern)
        theirs = re.compile(pattern)
        counts["entries"] = 0
        got = [(m.span(), m.groups()) for m in mine.finditer(text)]
        if got != [(m.span(), m.groups()) for m in theirs.finditer(text)]:
            print(f'prefilter differs: {pattern!r}')
            failed += 1
        n = counts["entries"]
        total += n
        if n > limit:
            print(f'prefilter: {pattern!r}: {n} matcher entries (limit {limit})')
            failed += 1
    print(f'prefilters: {total} matcher entries over {len(cases)} searches')
    return failed


def check_unicode_memos() -> int:
    # Case-insensitive and Unicode classes over text that repeats its non-ASCII code points: once
    # warm, a set that charset() must evaluate answers from its table's memo, and a case mapping
    # from _mapped()'s, with no bytecode evaluation and no binary search of the mapping tables.
    failed = total = 0
    original = sre.charset
    counted = {"charset": 0, "search": 0}

    def counted_charset(code, i, ch):
        counted["charset"] += 1
        return original(code, i, ch)

    class CountedKeys(list):
        def __getitem__(self, t):
            counted["search"] += 1
            return super().__getitem__(t)

    sre._mapped(0, 0x100)  # (decodes the tables, so that they can be wrapped)
    keys = sre._mapkeys
    sre._mapkeys = CountedKeys(keys)
    sre.charset = counted_charset
    cases = [
        (r"[A-Z_\u00c9\u03a3]+", re.I, "Ab\u212a\u017f\u00e9\u00c9\u03c3\u03a3_" * 100 + "!"),
        (r"\w+", 0, "\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440 " * 100),
        (r"(?i)[\u0400-\u04ff]+", 0, "\u0410\u0430\u0416\u0436 " * 100),
        (r"(?i)\u00e9t\u00e9", 0, "\u00c9T\u00c9 \u00e9t\u00e9 \u00e8 " * 100),
    ]
    try:
        for pattern, flags, text in cases:
            mine = port.compile(pattern, flags)
            theirs = re.compile(pattern, flags)
            mine.findall(text)  # (warms the memos)
            counted["charset"] = counted["search"] = 0
            if mine.findall(text) != theirs.findall(text):
                print(f'unicode memo differs: {pattern!r}')
                failed += 1
            n = counted["charset"] + counted["search"]
            total += n
            if n > 0:
                print(f'unicode memos: {pattern!r}: {counted["charset"]} charset() calls and '
                      f'{counted["search"]} mapping searches (limit 0)')
                failed += 1
    finally:
        sre.charset = original
        sre._mapkeys = keys
    print(f'unicode memos: {total} charset() calls and mapping searches over {len(cases)} warm cases (limit 0)')
    return failed


def check_branch_memos() -> int:
    # The bit-parallel filter of alternatives over text from U+0080: a character that none of their
    # leading literals and classes may match has no bits, untested, and once warm, one that some may
    # match answers from the filter's memo. _branch_bits(), which tests every item, is not called.
    failed = total = 0
    original = sre._branch_bits
    counted = {"bits": 0}

    def counted_bits(state, code, b, n, ch):
        counted["bits"] += 1
        return original(state, code, b, n, ch)

    cyr = "абвгдежзийклмнопрстуфхцчшщъыьэюя"
    words = ["привет", "мир", "ошибка", "сообщение", "журнал", "error", "запись"]
    russian = " ".join([words[(i * 5 + i // 3) % 7] for i in range(2000)])
    letters = "".join([cyr[(i * 7) % 32] for i in range(3000)])
    cases = [
        (r"(?:error|warning)", russian),
        (r"agggtaaa|tttaccct", letters),
        (r"[cgt]gggtaaa|tttaccc[acg]", russian),
        (r"(?:прив|мир)", russian),
        (r"(?:" + cyr[:31] + "|" + cyr[1:32] + ")", letters),
        (r"(?:[а-я][б-я]x|[в-я][г-я]y)", letters),
    ]
    sre._branch_bits = counted_bits
    try:
        for pattern, text in cases:
            mine = port.compile(pattern)
            theirs = re.compile(pattern)
            mine.findall(text)  # (builds the filter and warms its memo)
            counted["bits"] = 0
            if mine.findall(text) != theirs.findall(text):
                print(f'branch memo differs: {pattern!r}')
                failed += 1
            n = counted["bits"]
            total += n
            if n > 0:
                print(f'branch memos: {pattern!r}: {n} _branch_bits() calls (limit 0)')
                failed += 1
    finally:
        sre._branch_bits = original
    print(f'branch memos: {total} _branch_bits() calls over {len(cases)} warm cases (limit 0)')
    return failed


def main() -> int:
    paras, blocks = re_bench.inputs(20)
    failed = 0
    print(f"{'operation':30} {'entries':>8} {'contexts':>9}   (per input; limits over {len(paras)} inputs)")
    for name, pattern, flags, what, max_entries, max_contexts in OPERATIONS:
        mine = port.compile(pattern, flags)
        theirs = re.compile(pattern, flags)
        counts["entries"] = counts["contexts"] = 0
        texts = paras if what == "split" else blocks
        for text in texts:
            if run(mine, what, text) != run(theirs, what, text):
                print(f"{name}: lib/re's result differs from re's for {text!r}")
                failed += 1
        e = counts["entries"]
        c = counts["contexts"]
        over = e > max_entries or c > max_contexts
        failed += over
        print(f"{name:30} {e / len(texts):8.1f} {c / len(texts):9.1f}   ({e} of {max_entries}, {c} of {max_contexts}){'  OVER THE LIMIT' if over else ''}")
    failed += check_charset_allocations()
    failed += check_ignorecase_repeats()
    failed += check_ignorecase_searches()
    failed += check_repeat_prefixes()
    failed += check_class_spans()
    failed += check_nested_matches()
    failed += check_prefilters()
    failed += check_unicode_memos()
    failed += check_branch_memos()
    if "--time" in sys.argv:
        pys = sys.argv[sys.argv.index("--time") + 1]
        with tempfile.TemporaryDirectory() as d:
            exe = os.path.join(d, "re_bench")
            subprocess.run([pys, "build", os.path.join(ROOT, "tools", "re_bench.py"), "-o", exe], check=True)
            compiled = subprocess.run([exe, "--time"], capture_output=True, text=True, check=True).stdout.splitlines()
        cpython = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "re_bench.py"), "--time"],
                                 capture_output=True, text=True, check=True).stdout.splitlines()
        if compiled[0] != cpython[0]:
            print(f"the compiled {compiled[0]} differs from CPython's {cpython[0]}")
            failed += 1
        print(f"\n{'per call':30} {'compiled':>10} {'CPython':>10}   (median of 5 rounds over 200 inputs)")
        for a, b in zip(compiled[1:], cpython[1:]):
            print(f"{a.split()[0]:30} {a.split()[1]:>7} us {b.split()[1]:>7} us")
    print(f"{len(OPERATIONS)} operations, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
