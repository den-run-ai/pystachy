"""docs/concurrency.md's capability table names registered probes.

Each row of the table of current capabilities names at least one probe, a path in backquotes in its
last column; each probe exists, and a suite runs it: tests/run.sh every program, deviation and
rejection of the corpus (tests/corpus.sh's patterns), tests/ffi/run.sh its c_*.py and py_*.py cases
and the extension clients its loop lists, and tests/verify.sh the C probes of tools/ that it builds.
A probe that nothing runs, or a client left out of tests/ffi/run.sh's list, would leave its row
unchecked while the table still claimed it.

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


def clients(script: str) -> list:
    """the extension clients tests/ffi/run.sh runs: the words of its `for c in ...; do` loop"""
    m = re.search(r"^\s*for c in ([^;]*); do$", script, re.M)
    return m.group(1).split() if m else []


def runner(path: str, run_ffi: str, verify: str) -> str:
    """the suite that runs the probe at path, or "" if none does"""
    if path.endswith("/"):  # an area of the corpus: its cases
        cases = [f for f in os.listdir(os.path.join(ROOT, path)) if f.endswith(".py")]
        return "tests/run.sh" if cases and any(fnmatch.fnmatch(path + cases[0], p) for p in CORPUS) else ""
    if any(fnmatch.fnmatch(path, p) for p in CORPUS):
        return "tests/run.sh"
    if fnmatch.fnmatch(path, "tests/ffi/c_*.py") or fnmatch.fnmatch(path, "tests/ffi/py_*.py"):
        return "tests/ffi/run.sh"
    if fnmatch.fnmatch(path, "tests/ffi/ext/*.py"):
        return "tests/ffi/run.sh" if os.path.basename(path) in clients(run_ffi) else ""
    if fnmatch.fnmatch(path, "tools/*.c"):
        return "tests/verify.sh" if path in verify else ""
    return ""


class CapabilityProbes(unittest.TestCase):
    def setUp(self):
        self.rows = capabilities(read("docs/concurrency.md"))
        self.run_ffi = read("tests/ffi/run.sh")
        self.verify = read("tests/verify.sh")

    def test_table_found(self):
        self.assertGreater(len(self.rows), 5, "the capability table of docs/concurrency.md")
        self.assertIn("pwclient.py", clients(self.run_ffi))

    def test_rows_name_registered_probes(self):
        for capability, status, probes in self.rows:
            with self.subTest(capability=capability):
                self.assertTrue(probes, "a row names at least one probe")
                for p in probes:
                    self.assertTrue(os.path.exists(os.path.join(ROOT, p)), f"{p} does not exist")
                    self.assertTrue(runner(p, self.run_ffi, self.verify), f"no suite runs {p}")

    def test_runner(self):
        self.assertEqual(runner("tests/ffi/ext/pk3.py", "    for c in client.py pk3.py; do", ""), "tests/ffi/run.sh")
        self.assertEqual(runner("tests/ffi/ext/pk3.py", "    for c in client.py; do", ""), "")
        self.assertEqual(runner("tests/ffi/ext/mg.py", "    for c in pk3.py; do", ""), "")  # (a module, not a client)
        self.assertEqual(runner("tests/programs/library/lib_thread.py", "", ""), "tests/run.sh")
        self.assertEqual(runner("tests/lib_thread.py", "", ""), "")  # (a stray: no run finds it)
        self.assertEqual(runner("tools/selectprobe.c", "", "tools/selectprobe.c"), "tests/verify.sh")
        self.assertEqual(runner("tools/thread_check.py", "", ""), "")


if __name__ == "__main__":
    unittest.main()
