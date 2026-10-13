"""re_probe: what lib/re does for textwrap's regular expressions, counted, and optionally timed.

lib/re is ordinary Python, so CPython runs it as a package of its own (pys_re, as in
tools/re_fuzz.py). On re_bench.inputs(20), 20 paragraphs and 20 blocks made as tools/re_bench.py
makes its inputs (the paragraphs are the first 20 it times; the blocks, drawn after them, are not
the ones it times), it runs each operation of textwrap's patterns, checks its result against
CPython's re, and counts the matcher's entries (calls of _sre.sre_match: a search's attempts, and
sre_count()'s nested ones), the contexts it makes (_sre.Ctx objects), and their activations
(including reused contexts for assertions, alternatives and repeats). The counts are
deterministic: the run fails if one is above its limit, so a change to lib/re that makes the matcher
do more fails here, and one that makes it do less lowers the limits.

The time of a call of lib/re under CPython says little about compiled code: --time PYSTACHY builds
tools/re_bench.py with that compiler and prints each operation's time per call, compiled and under
CPython's own re, for information only.

usage: python3 tools/re_probe.py [--time PYSTACHY]   (make re-probe; a step of make verify)
"""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import re_bench  # noqa: E402  (the patterns and the inputs)

_spec = importlib.util.spec_from_file_location("pys_re", os.path.join(ROOT, "lib", "re", "__init__.py"),
                                               submodule_search_locations=[os.path.join(ROOT, "lib", "re")])
port = importlib.util.module_from_spec(_spec)
sys.modules["pys_re"] = port
_spec.loader.exec_module(port)
sre = sys.modules["pys_re._sre"]
counts = {"entries": 0, "contexts": 0, "activations": 0}
_sre_match = sre.sre_match
_Ctx = sre.Ctx


def _counted_match(state, code, start, toplevel):
    counts["entries"] += 1
    return _sre_match(state, code, start, toplevel)


class _CountedCtx(_Ctx):
    def __init__(self, *args):
        counts["contexts"] += 1
        counts["activations"] += 1
        super().__init__(*args)

    def reuse(self, *args):
        counts["activations"] += 1
        super().reuse(*args)


sre.sre_match = _counted_match
sre.Ctx = _CountedCtx

# name, pattern, flags, what it does to what, and limits of entries, contexts and activations
# over the 20 inputs
OPERATIONS = [
    ("wordsep_re.split", re_bench.WORDSEP, re.VERBOSE, "split", 3414, 140, 47381),
    ("wordsep_simple_re.split", re_bench.WORDSEP_SIMPLE, 0, "split", 1580, 40, 3160),
    ("whitespace_only_re.sub", re_bench.WHITESPACE_ONLY, re.MULTILINE, "sub", 320, 40, 1327),
    ("leading_whitespace_re.findall", re_bench.LEADING_WHITESPACE, re.MULTILINE, "findall", 320, 40, 733),
    ("margin.sub", r"(?m)^    ", 0, "sub", 298, 20, 298),
]


def run(rx, what: str, text: str):
    if what == "split":
        return rx.split(text)
    if what == "sub":
        return rx.sub("", text)
    return rx.findall(text)


def main() -> int:
    paras, blocks = re_bench.inputs(20)
    failed = 0
    print(f"{'operation':30} {'entries':>8} {'contexts':>9} {'active':>9}   (per input; limits over {len(paras)} inputs)")
    for name, pattern, flags, what, max_entries, max_contexts, max_activations in OPERATIONS:
        mine = port.compile(pattern, flags)
        theirs = re.compile(pattern, flags)
        counts["entries"] = counts["contexts"] = counts["activations"] = 0
        texts = paras if what == "split" else blocks
        for text in texts:
            if run(mine, what, text) != run(theirs, what, text):
                print(f"{name}: lib/re's result differs from re's for {text!r}")
                failed += 1
        e = counts["entries"]
        c = counts["contexts"]
        a = counts["activations"]
        over = e > max_entries or c > max_contexts or a > max_activations
        failed += over
        print(f"{name:30} {e / len(texts):8.1f} {c / len(texts):9.1f} {a / len(texts):9.1f}   ({e} of {max_entries}, {c} of {max_contexts}, {a} of {max_activations}){'  OVER THE LIMIT' if over else ''}")
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
