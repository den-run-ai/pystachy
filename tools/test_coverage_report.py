"""tools/coverage_report.py: the checks that keep an incomplete measurement out of a report, and the
native runtime's summary.

Run with python3 -m unittest discover -s tools -p test_coverage_report.py.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import coverage_report  # noqa: E402


def part(d, name, suite, shard=None, processes=10, data_files=None, commit="c0", data=True):
    os.makedirs(os.path.join(d, "parts"), exist_ok=True)
    m = {"part": name, "suite": suite, "shard": shard, "selected": False, "cases": None, "report": "1 passed, 0 failed",
         "processes": processes, "data_files": processes if data_files is None else data_files, "seconds": 1,
         "commit": commit, "dirty": False}
    with open(os.path.join(d, "parts", name + ".json"), "w", encoding="utf-8") as f:
        json.dump(m, f)
    if data:
        open(os.path.join(d, "parts", "data." + name), "w").close()


class PctTests(unittest.TestCase):
    def test_coverage_py_rounding(self):
        self.assertEqual(coverage_report.pct(0, 0), "-")
        self.assertEqual(coverage_report.pct(0, 5), "0.0%")
        self.assertEqual(coverage_report.pct(1, 3), "33.3%")
        self.assertEqual(coverage_report.pct(1, 2000), "0.1%")       # 0.05: never shown as 0.0
        self.assertEqual(coverage_report.pct(1999, 2000), "99.9%")   # 99.95: never shown as 100.0
        self.assertEqual(coverage_report.pct(5, 5), "100.0%")


class ChecksTests(unittest.TestCase):
    def test_shards_summed(self):
        parts = [{"report": "10 passed, 0 failed"}, {"report": "7 passed, 1 failed"}]
        self.assertEqual(coverage_report.checks(parts), "17 passed, 1 failed")

    def test_other_reports_kept(self):
        self.assertEqual(coverage_report.checks([{"report": "85 tests, OK"}]), "85 tests, OK")
        parts = [{"report": "10 passed, 0 failed"}, {"report": "the IR check and llvm-as accept the IR of 3 programs"}]
        self.assertEqual(coverage_report.checks(parts), "10 passed, 0 failed; the IR check and llvm-as accept the IR of 3 programs")


class PartsTests(unittest.TestCase):
    def errors(self, *parts):
        with tempfile.TemporaryDirectory() as d:
            for p in parts:
                part(d, *p[0], **p[1])
            return coverage_report.parts_of(d)[1]

    def test_complete(self):
        self.assertEqual(self.errors((("corpus-0", "corpus"), {"shard": [0, 3]}), (("corpus-1", "corpus"), {"shard": [1, 3]}),
                                     (("corpus-2", "corpus"), {"shard": [2, 3]}), (("ffi", "ffi"), {}),
                                     (("cache", "cache"), {"processes": 40, "data_files": 39}), (("unit", "unit"), {})), [])

    def test_missing_shard(self):
        e = self.errors((("corpus-0", "corpus"), {"shard": [0, 3]}), (("corpus-2", "corpus"), {"shard": [2, 3]}))
        self.assertEqual(len(e), 1)
        self.assertIn("not all 3", e[0])

    def test_suite_twice(self):
        e = self.errors((("corpus", "corpus"), {}), (("corpus-0", "corpus"), {"shard": [0, 2]}))
        self.assertTrue(any("measured 2 times" in x for x in e), e)

    def test_lost_data(self):
        self.assertIn("9 coverage data files, for 10 processes", self.errors((("ffi", "ffi"), {"data_files": 9}))[0])
        # only tests/cache.sh's killed build may leave none
        self.assertEqual(self.errors((("cache", "cache"), {"processes": 10, "data_files": 9})), [])
        self.assertTrue(self.errors((("cache", "cache"), {"processes": 10, "data_files": 10})))
        self.assertTrue(self.errors((("unit", "unit"), {"processes": 0, "data_files": 0})))
        self.assertIn("no data", self.errors((("unit", "unit"), {"data": False}))[0])

    def test_commits(self):
        e = self.errors((("ffi", "ffi"), {"commit": "a"}), (("unit", "unit"), {"commit": "b"}))
        self.assertIn("different commits", e[0])

    def test_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("no parts", coverage_report.parts_of(d)[1][0])


LCOV = """SF:runtime.c
FN:3,a
FN:8,b
FNDA:4,a
FNDA:0,b
DA:3,4
DA:4,4
DA:8,0
DA:9,0
BRDA:4,0,0,4
BRDA:4,0,1,0
BRDA:9,0,0,-
BRDA:9,0,1,-
end_of_record
SF:pyext.c
FN:1,pys_init
FNDA:2,pys_init
DA:1,2
end_of_record
"""
SOURCE = "/* the declarations */\n/* ---------- one: the first ----------\n   more */\nint a;\n\n\n/* ---------- two ---------- */\nint b;\n"


def summary(name, lines, branches, functions, regions):
    def s(c, t):
        return {"count": t, "covered": c, "notcovered": t - c, "percent": 100.0 * c / t if t else 0}
    return {"filename": name, "summary": {"lines": s(*lines), "branches": s(*branches), "functions": s(*functions), "regions": s(*regions)}}


class RuntimeTests(unittest.TestCase):
    def test_summary(self):
        with tempfile.TemporaryDirectory() as d:
            files = [summary("./runtime.c", (2, 4), (1, 4), (1, 2), (3, 6)), summary("pyext.c", (1, 1), (0, 0), (1, 1), (1, 1))]
            total = summary("", (3, 5), (1, 4), (2, 3), (4, 7))["summary"]
            with open(os.path.join(d, "coverage.json"), "w", encoding="utf-8") as f:
                json.dump({"data": [{"files": files, "totals": total}]}, f)
            with open(os.path.join(d, "lcov.info"), "w", encoding="utf-8") as f:
                f.write(LCOV)
            with open(os.path.join(d, "suites.tsv"), "w", encoding="utf-8") as f:
                f.write("corpus\t10 passed, 0 failed\t5\n")
            with open(os.path.join(d, "runtime.c"), "w", encoding="utf-8") as f:
                f.write(SOURCE)
            with open(os.devnull, "w") as null:
                out, sys.stdout = sys.stdout, null
                try:
                    self.assertEqual(coverage_report.runtime(d, "abc", "false", os.path.join(d, "runtime.c")), 0)
                finally:
                    sys.stdout = out
            with open(os.path.join(d, "summary.md"), encoding="utf-8") as f:
                text = f.read()
            with open(os.path.join(d, "badge.json"), encoding="utf-8") as f:
                b = json.load(f)
        self.assertIn("lines **60.0%** (3 of 5) and branches **25.0%** (1 of 4)", text)
        self.assertIn("| `runtime.c` | 4 | 2 | 50.0% | 4 | 3 | 25.0% | 50.0% | 50.0% |", text)
        # sections: a's lines and its taken branch in "one: the first", b's in "two"
        self.assertIn("| one: the first | 2 | 2 | 100.0% | 2 | 50.0% | 1 | 100.0% |", text)
        self.assertIn("| two | 7 | 2 | 0.0% | 2 | 0.0% | 1 | 0.0% |", text)
        self.assertNotIn("(declarations)", text)   # no line of it is counted
        self.assertEqual(b["message"], "60.0% lines, 25.0% branches")
        self.assertEqual(b["color"], "red")          # the lower one's


if __name__ == "__main__":
    unittest.main()
