"""The crossing matrix's four copies agree: tools/crossing_matrix.json, the table in
docs/dynamic-any.md, the differential test of each column and the rejection test of each limit.

No compiler is needed: tools/crossing_matrix.py --check probes the cells again with one, and the
test suite runs the tests named here.
"""

import json
import os
import unittest

import crossing_matrix as cm


def read(path):
    with open(os.path.join(cm.ROOT, path), encoding="utf-8") as f:
        return f.read()


class CrossingMatrixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(read(cm.DATA))

    def test_every_cell_is_recorded_and_none_is_wrong(self):
        cells = self.data["cells"]
        for c, _ in cm.COLUMNS:
            for row in cm.ROWS:
                with self.subTest(column=c, row=row[0]):
                    v = cells.get(c, {}).get(row[0])
                    if cm.cell(c, row) is None:
                        self.assertIsNone(v)
                    else:
                        self.assertIsNotNone(v, "run tools/crossing_matrix.py --write")
                        self.assertIn(v[0], ["yes", "no"])
                        self.assertEqual(len(v), 2 if v[0] == "yes" else 3)
        known = {c for c, _ in cm.COLUMNS}
        self.assertEqual(set(cells) - known, set())
        for c, rows in cells.items():
            self.assertEqual(set(rows) - {r[0] for r in cm.ROWS}, set(), c)

    def test_limits_match_the_cells(self):
        want = {}
        for lim, (aspect, _, where) in cm.limits_of(self.data["cells"]).items():
            want[lim] = (aspect, where)
        got = {lim: (info["aspect"], info["cells"]) for lim, info in self.data["limits"].items()}
        self.assertEqual(got, want)

    def test_limits_match_the_cells_and_the_tests(self):
        self.assertEqual(self.data["tests"], cm.rejections(self.data["cells"]))
        for path, (where, aspect, expect) in self.data["tests"].items():
            with self.subTest(test=path):
                c, r = where.split("__")
                message = dict(cm.rejected(self.data["cells"][c][r]))[aspect]
                self.assertIn(expect, message)
                lim = cm.limit(message)
                self.assertIn(where, self.data["limits"][lim]["cells"])
                held = ("store", "convert")  # (one limit's cells may be rejected at either)
                self.assertTrue(self.data["limits"][lim]["aspect"] == aspect or (aspect in held and self.data["limits"][lim]["aspect"] in held))
                with open(os.path.join(cm.ROOT, path), encoding="utf-8") as f:
                    self.assertEqual(f.readline(), "# error: " + expect + "\n")

    def test_generated_tests_are_current(self):
        keep = cm.generated(self.data)
        for path, text in keep.items():
            with self.subTest(path=path):
                self.assertEqual(read(path), text, "run tools/crossing_matrix.py --write")
                if path.startswith(cm.PROGRAMS):
                    self.assertTrue(os.path.exists(os.path.join(cm.ROOT, path[:-3] + ".out")), "record " + path)
        for d in [cm.PROGRAMS, cm.ERRORS]:
            for n in sorted(os.listdir(os.path.join(cm.ROOT, d))):
                if n.startswith("crossing_"):
                    self.assertIn(f"{d}/{n[: n.rfind('.')]}.py", keep, f"{d}/{n} is no test of the matrix")

    def test_each_supported_row_has_its_function(self):
        for c, rows in self.data["cells"].items():
            names = [r for r, v in rows.items() if cm.held(v)]
            if not names:
                continue
            text = read(f"{cm.PROGRAMS}/crossing_{c}.py")
            for r in names:
                with self.subTest(column=c, row=r):
                    self.assertIn(f"\ndef cross_{r}() -> None:\n", text)
                    self.assertIn(f"\ncross_{r}()\n", text)

    def test_the_table_is_current(self):
        doc = read(cm.DOC)
        self.assertIn(cm.START, doc)
        self.assertIn(cm.END, doc)
        shown = doc.split(cm.START, 1)[1].split(cm.END, 1)[0].strip("\n").split("\n")
        self.assertEqual(shown, cm.table(self.data), "run tools/crossing_matrix.py --write")

    def test_a_rejection_test_expects_the_message_as_printed(self):
        message = "'object' object has no method 'describe' (narrow a value of object with isinstance() to int first)"
        self.assertEqual(cm.expected(message), "'object' object has no method")
        named = "narrowing 'x' by isinstance() is not supported here (use a local)"
        self.assertEqual(cm.expected(named), "narrowing 'x' by isinstance() is not supported here")
        made = "a bytes value cannot become an Any value (making the table of bytes as object (for Any), converted at x.py:3)"
        self.assertEqual(cm.expected(made), "cannot become an Any value")
        fn = "expected object, got <function main.<locals>.<lambda> (x.py:3)>: a function or Callable value as a value of object is not supported yet: call it, or store a <function f> where one is expected"
        self.assertEqual(cm.expected(fn), "a function or Callable value as a value of object is not supported yet")
        for m in [message, made, fn]:
            self.assertIn(cm.expected(m), m)

    def test_limit_text_drops_the_value_and_the_advice(self):
        self.assertEqual(cm.limit("a bytes value cannot become an Any value (making the table of bytes as object (for Any), converted at x.py:3)"), "cannot become an Any value")
        self.assertEqual(cm.limit("expected object, got <function f>: a function or Callable value as a value of object is not supported yet: call it, or store a <function f> where one is expected"), "a function or Callable value as a value of object is not supported yet")
        self.assertEqual(cm.limit("frozenset[int] in a closed union is not supported (use scalar, list/dict or native class/file types)"), "in a closed union is not supported")
        self.assertEqual(cm.limit("object of type 'object' has no len() (narrow a value of object with isinstance() to int)"), "object of type 'object' has no len()")

    def test_a_rejection_where_a_value_is_stored_is_blamed_on_the_statement_that_asked(self):
        message = "comparing a range with bool | None is not supported (making the table of bool | None as object (for range == its object), converted at x.py:4)"
        self.assertEqual(cm.blamed("store", message, {}), "equal")
        self.assertEqual(cm.blamed("store", message, {"equal": "x"}), "store")
        self.assertEqual(cm.blamed("identity", "'is' is only supported for objects and None", {}), "identity")


if __name__ == "__main__":
    unittest.main()
