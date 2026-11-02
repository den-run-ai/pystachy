"""Tests of tools/cpython_test_methods.py's mechanical unittest extraction."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpython_test_methods as ctm

SOURCE = '''
import unittest
from test import support
from test.support import import_helper

py_bisect = import_helper.import_fresh_module('bisect', blocked=['_bisect'])
c_bisect = import_helper.import_fresh_module('bisect', fresh=['_bisect'])
LIMIT = 3


def helper(x):
    return x * 2


def unused():
    return support.verbose


class Point:
    def __init__(self, x):
        self.x = x


class BisectMixin:
    def test_module_attribute(self):
        self.assertEqual(self.module.bisect_left([1, 2, 3], 2), 1)
        mod = self.module
        self.assertEqual(mod.bisect_right([1, 2, 3], 2), 2)


class BisectPython(BisectMixin, unittest.TestCase):
    module = py_bisect


@unittest.skipUnless(c_bisect, 'requires _bisect')
class BisectC(BisectMixin, unittest.TestCase):
    module = c_bisect


class BaseMixin:
    def setUp(self):
        self.base = self.module.bisect_left([1, 2], 2)


class MiddleMixin(BaseMixin):
    def setUp(self):
        super().setUp()
        self.middle = 2


class RegexTests(unittest.TestCase):
    def test_regex(self):
        self.assertRegex('spam and eggs', 'and')

    def test_raises_regex_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'nomatch'):
            int('bad')

    def test_raises_regex_call_mismatch(self):
        self.assertRaisesRegex(ValueError, 'nomatch', int, 'bad')


class OtherTests(unittest.TestCase):
    def test_asserts(self):
        only_in_other_tests()

    def test_other(self):
        self.assertTrue(LIMIT)


class ChainTests(MiddleMixin, unittest.TestCase):
    module = py_bisect

    def test_chain(self):
        self.assertEqual((self.base, self.middle), (1, 2))


class SampleTests(unittest.TestCase):
    def setUp(self):
        self.items = [1, 2, LIMIT]

    def test_asserts(self):
        eq = self.assertEqual
        eq(helper(2), 4)
        self.assertTrue(self.items)
        self.assertIn(2, self.items)
        self.assertIsNone(None)
        self.assertAlmostEqual(0.1 + 0.2, 0.3)
        self.assertIsInstance(Point(1), Point)
        for i in range(2):
            with self.subTest(i=i):
                self.assertLess(i, LIMIT)

    def test_raises(self):
        self.assertRaises(ZeroDivisionError, divmod, 1, 0)
        with self.assertRaises(KeyError) as cm:
            {}['missing']
        self.assertEqual(cm.exception.args, ('missing',))
        with self.assertRaisesRegex(ValueError, 'bad'):
            int('bad')

    def test_false_assertion(self):
        self.assertEqual(helper(1), 3)

    def test_nothing_raised(self):
        with self.assertRaises(ValueError):
            int('7')

    def test_fail(self):
        self.fail('reached')

    def test_warns(self):
        with self.assertWarns(DeprecationWarning):
            pass

    @support.cpython_only
    def test_implementation_detail(self):
        pass

    @unittest.skip('never')
    def test_skipped(self):
        pass


if __name__ == '__main__':
    unittest.main()
'''


def run(path):
    return subprocess.run([sys.executable, "-I", str(path)], capture_output=True, text=True, timeout=60)


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.src = self.dir / "test_sample.py"
        self.src.write_text(SOURCE)
        self.out = self.dir / "out"
        self.tests, self.left = ctm.extract(str(self.src), str(self.out))

    def tearDown(self):
        self.tmp.cleanup()

    def program(self, name):
        return self.out / f"{name}.py"

    def test_selection(self):
        self.assertEqual(sorted(f"{c}.{m}" for c, m in self.tests), [
            "BisectPython.test_module_attribute", "ChainTests.test_chain", "OtherTests.test_asserts",
            "OtherTests.test_other", "RegexTests.test_raises_regex_call_mismatch",
            "RegexTests.test_raises_regex_mismatch", "RegexTests.test_regex", "SampleTests.test_asserts", "SampleTests.test_fail",
            "SampleTests.test_false_assertion", "SampleTests.test_nothing_raised", "SampleTests.test_raises",
            "SampleTests.test_warns"])
        self.assertEqual(sorted(m for _, m, _ in self.left), ["test_implementation_detail", "test_skipped"])

    def test_passing_programs_run_without_unittest(self):
        for name in ("SampleTests__test_asserts", "SampleTests__test_raises", "BisectPython__test_module_attribute",
                     "ChainTests__test_chain"):
            text = self.program(name).read_text()
            self.assertNotIn("unittest", text)
            self.assertNotIn("import_helper", text)
            r = run(self.program(name))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, f"ok {name.replace('__', '.')}\n")

    def test_assertions_are_kept(self):
        # negative controls: a false assertion and an exception that is not raised still fail
        r = run(self.program("SampleTests__test_false_assertion"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("AssertionError", r.stderr)
        r = run(self.program("SampleTests__test_nothing_raised"))
        self.assertIn("did not raise", r.stderr)
        r = run(self.program("SampleTests__test_fail"))
        self.assertIn("AssertionError: reached", r.stderr)

    def test_regexes_are_checked(self):
        # the sample file does not import re: the programs that need it bind it
        r = run(self.program("RegexTests__test_regex"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("import re", self.program("RegexTests__test_regex").read_text())
        self.assertNotIn("import re", self.program("SampleTests__test_asserts").read_text())
        for name in ("RegexTests__test_raises_regex_mismatch", "RegexTests__test_raises_regex_call_mismatch"):
            r = run(self.program(name))
            self.assertNotEqual(r.returncode, 0, name)
            self.assertIn("AssertionError", r.stderr, name)

    def test_unsupported_feature_raises_instead_of_passing(self):
        r = run(self.program("SampleTests__test_warns"))
        self.assertIn("NotImplementedError", r.stderr)
        self.assertNotIn("ok ", r.stdout)

    def test_programs_keep_only_what_they_use(self):
        text = self.program("SampleTests__test_raises").read_text()
        self.assertNotIn("def test_asserts", text)
        self.assertNotIn("def unused", text)
        self.assertNotIn("class BisectC", self.program("BisectPython__test_module_attribute").read_text())
        self.assertIn("import bisect as py_bisect", self.program("BisectPython__test_module_attribute").read_text())

    def test_setup_becomes_init(self):
        text = self.program("SampleTests__test_asserts").read_text()
        self.assertIn("def __init__(self):", text)
        self.assertNotIn("t.setUp()", text)
        out = self.dir / "kept"
        ctm.extract(str(self.src), str(out), setup_init=False)
        text = (out / "SampleTests__test_asserts.py").read_text()
        self.assertIn("def setUp(self):", text)
        self.assertIn("t.setUp()", text)
        self.assertEqual(run(out / "SampleTests__test_asserts.py").returncode, 0)

    def test_combine_runs_the_selection_in_order(self):
        combined = self.dir / "combined.py"
        ctm.main(["combine", str(self.src), str(combined), "SampleTests.test_raises", "SampleTests.test_asserts",
                  "BisectPython.test_module_attribute"])
        r = run(combined)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split("\n")[:3], ["ok SampleTests.test_raises", "ok SampleTests.test_asserts",
                                                    "ok BisectPython.test_module_attribute"])

    def test_a_test_stays_in_its_own_class(self):
        # OtherTests also has a test_asserts, which must not come along with SampleTests's
        combined = self.dir / "combined.py"
        ctm.main(["combine", str(self.src), str(combined), "SampleTests.test_asserts", "OtherTests.test_other"])
        self.assertNotIn("only_in_other_tests", combined.read_text())
        r = run(combined)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "ok SampleTests.test_asserts\nok OtherTests.test_other\n")

    def test_triage_reports_files_it_cannot_read(self):
        out = self.dir / "triage.json"
        with self.assertRaises(SystemExit), open(os.devnull, "w") as null:
            stderr, sys.stderr = sys.stderr, null
            try:
                ctm.triage(["true"], 1, str(out), str(self.dir / "work"), [str(self.dir / "test_missing.py")])
            finally:
                sys.stderr = stderr
        report = json.loads(out.read_text())
        self.assertEqual(report["records"], [])
        self.assertIn("FileNotFoundError", report["errors"][str(self.dir / "test_missing.py")])

    def test_combine_refuses_unknown_tests(self):
        with self.assertRaises(SystemExit), open(os.devnull, "w") as null:
            stderr, sys.stderr = sys.stderr, null
            try:
                ctm.main(["combine", str(self.src), str(self.dir / "x.py"), "SampleTests.test_skipped"])
            finally:
                sys.stderr = stderr


if __name__ == "__main__":
    unittest.main()
