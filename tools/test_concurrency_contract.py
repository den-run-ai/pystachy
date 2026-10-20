"""docs/concurrency.md's capability table names registered probes.

Each row of the table of current capabilities names at least one probe, a path in backquotes in its
last column; each probe exists, and code that a suite executes runs it, comments aside: tests/run.sh
every program, deviation and rejection of the corpus (tests/corpus.sh's patterns); tests/ffi/run.sh
its c_*.py and py_*.py cases through their loops and the extension clients its client loop lists,
while tests/verify.sh's ffi step, in its plan of every step, runs tests/ffi/run.sh; and a step of
that plan builds each C probe of tools/. A probe that nothing runs, or that only a comment names,
would leave its row unchecked while the table still claimed it.

Run with python3 -m unittest discover -s tools -p test_concurrency_contract.py.
"""
import fnmatch
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = ["tests/programs/*/*.py", "tests/deviations/*.py", "tests/errors/*/*.py"]


def read(path: str) -> str:
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def capabilities(text: str) -> list:
    """[(capability, status, [probe paths])]: the rows of the first table of the Capabilities section"""
    section = text.split("\n## Capabilities\n", 1)[1].split("\n## ", 1)[0]
    lines = section.split("\n| Capability | Status | Probes |\n", 1)[1].splitlines()
    rows = []
    for line in lines[1:]:  # (after the |---| line)
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip("|").split(" | ")]
        rows.append((cells[0], cells[1], re.findall(r"`([^`]+)`", cells[-1])))
    return rows


def code(line: str) -> str:
    """a line of shell without its comment: from a # that starts a word outside quotes"""
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == quote:
                quote = ""
            elif ch == "\\" and quote == '"':
                i += 1
        elif ch == "\\":
            i += 1
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t;"):
            return line[:i].rstrip()
        i += 1
    return line.rstrip()


def code_lines(script: str) -> list:
    return [c for c in (code(line) for line in script.splitlines()) if c.strip()]


def clients(script: str) -> list:
    """the extension clients tests/ffi/run.sh runs: the words of its `for c in ...; do` loop"""
    for line in code_lines(script):
        m = re.fullmatch(r"\s*for c in ([^;]*); do", line)
        if m:
            return m.group(1).split()
    return []


def planned(verify: str) -> set:
    """the steps of tests/verify.sh's plan of every step (its plan() for all)"""
    for line in code_lines(verify):
        m = re.fullmatch(r"\s*all\) echo '([^']*)' ;;", line)
        if m:
            return set(m.group(1).split())
    return set()


def steps(verify: str) -> dict:
    """{step: its code lines}: the body of each `if want STEP ...; then` ... `fi` block of
    tests/verify.sh (both at the start of a line), under every step its condition names"""
    out: dict = {}
    names = None
    body: list = []
    for line in code_lines(verify):
        if names is None:
            if re.match(r"if want [^;]*; then$", line):
                names = re.findall(r"\bwant ([A-Za-z0-9-]+)", line)
                body = []
        elif line == "fi":
            for n in names:
                out.setdefault(n, []).extend(body)
            names = None
        else:
            body.append(line)
    return out


def runs(verify: str, needle: str) -> bool:
    """does a step of the plan of every step run a line of code that names needle?"""
    plan = planned(verify)
    return any(n in plan and any(needle in line for line in body) for n, body in steps(verify).items())


def runner(path: str, run_ffi: str, verify: str) -> str:
    """the suite that runs the probe at path, or "" if none does"""
    if path.endswith("/"):  # an area of the corpus: its cases
        cases = [f for f in os.listdir(os.path.join(ROOT, path)) if f.endswith(".py")]
        return "tests/run.sh" if cases and any(fnmatch.fnmatch(path + cases[0], p) for p in CORPUS) else ""
    if any(fnmatch.fnmatch(path, p) for p in CORPUS):
        return "tests/run.sh"
    if fnmatch.fnmatch(path, "tests/ffi/*.py") or fnmatch.fnmatch(path, "tests/ffi/ext/*.py"):
        if not runs(verify, "tests/ffi/run.sh"):
            return ""
        lines = code_lines(run_ffi)
        for glob in ("tests/ffi/c_*.py", "tests/ffi/py_*.py"):
            if fnmatch.fnmatch(path, glob):
                return "tests/ffi/run.sh" if any(re.fullmatch(r"\s*for f in " + re.escape(glob) + "; do", line) for line in lines) else ""
        if fnmatch.fnmatch(path, "tests/ffi/ext/*.py"):
            return "tests/ffi/run.sh" if os.path.basename(path) in clients(run_ffi) else ""
        return ""
    if fnmatch.fnmatch(path, "tools/*.c"):
        return "tests/verify.sh" if runs(verify, path) else ""
    return ""


def without(text: str, pattern: str) -> str:
    """text with the one match of the multiline regular expression pattern removed"""
    m = re.search(pattern, text, re.M | re.S)
    assert m, pattern
    return text[:m.start()] + text[m.end():]


class CapabilityProbes(unittest.TestCase):
    def setUp(self):
        self.rows = capabilities(read("docs/concurrency.md"))
        self.run_ffi = read("tests/ffi/run.sh")
        self.verify = read("tests/verify.sh")

    def test_table_found(self):
        self.assertGreater(len(self.rows), 5, "the capability table of docs/concurrency.md")
        self.assertIn("pwclient.py", clients(self.run_ffi))
        self.assertIn("select-io", planned(self.verify))

    def test_rows_name_registered_probes(self):
        for capability, status, probes in self.rows:
            with self.subTest(capability=capability):
                self.assertTrue(probes, "a row names at least one probe")
                for p in probes:
                    self.assertTrue(os.path.exists(os.path.join(ROOT, p)), f"{p} does not exist")
                    self.assertTrue(runner(p, self.run_ffi, self.verify), f"no suite runs {p}")

    def test_registered_on_this_tree(self):
        for p, suite in [("tests/ffi/ext/pk3.py", "tests/ffi/run.sh"), ("tests/ffi/py_exe.py", "tests/ffi/run.sh"),
                         ("tests/programs/library/lib_thread.py", "tests/run.sh"), ("tools/selectprobe.c", "tests/verify.sh")]:
            self.assertEqual(runner(p, self.run_ffi, self.verify), suite, p)
        self.assertEqual(runner("tests/ffi/ext/mg.py", self.run_ffi, self.verify), "")  # (a module, not a client)
        self.assertEqual(runner("tests/lib_thread.py", self.run_ffi, self.verify), "")  # (a stray: no run finds it)
        self.assertEqual(runner("tools/thread_check.py", self.run_ffi, self.verify), "")

    def test_removed_probe_is_unregistered(self):
        # negative controls, each made from this tree's own files: what remains is only a comment
        # naming the probe, or code that no step of the plan runs
        no_block = without(self.verify, r"^if want select-io; then\n.*?^fi\n")
        self.assertIn("selectprobe.c", no_block)  # (the header comment still names it)
        self.assertEqual(runner("tools/selectprobe.c", self.run_ffi, no_block), "")
        plan = next(line for line in self.verify.splitlines() if re.fullmatch(r"\s*all\) echo '[^']*' ;;", line))
        unplanned = self.verify.replace(plan, plan.replace(" select-io ", " "), 1)
        self.assertNotIn("select-io", planned(unplanned))
        self.assertEqual(runner("tools/selectprobe.c", self.run_ffi, unplanned), "")
        commented = no_block.replace("if want ffi; then\n", "if want ffi; then\n# tools/selectprobe.c\n", 1)
        self.assertEqual(runner("tools/selectprobe.c", self.run_ffi, commented), "")
        no_ffi = without(self.verify, r"^if want ffi; then\n.*?^fi\n")
        for p in ("tests/ffi/ext/pk3.py", "tests/ffi/py_exe.py"):
            self.assertEqual(runner(p, self.run_ffi, no_ffi), "", p)
        loop = next(line for line in self.run_ffi.splitlines() if re.fullmatch(r"\s*for c in [^;]*; do", line))
        no_clients = self.run_ffi.replace(loop, "#" + loop, 1)
        self.assertEqual(runner("tests/ffi/ext/pk3.py", no_clients, self.verify), "")
        no_py = self.run_ffi.replace("for f in tests/ffi/py_*.py; do", "for f in; do", 1)
        self.assertEqual(runner("tests/ffi/py_exe.py", no_py, self.verify), "")

    def test_code(self):
        self.assertEqual(code("  run tools/x.c  # tools/y.c"), "  run tools/x.c")
        self.assertEqual(code("echo '# kept' \"# kept\" ${n#x} $#"), "echo '# kept' \"# kept\" ${n#x} $#")
        self.assertEqual(code("# all of it"), "")


if __name__ == "__main__":
    unittest.main()
