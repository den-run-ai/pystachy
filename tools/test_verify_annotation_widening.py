"""Negative controls for CPython qualification and the bounded annotation transform."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import annotation_widening as widen

HEADER = b"# pystachy: dynamic-any\nfrom typing import Any as Dynamic\n"


class AnnotationWideningTests(unittest.TestCase):
    def test_edits_only_resolved_signatures_preserving_source_and_integer_policy(self):
        source = b"# pystachy: python-int\n" + HEADER + "def café(n: int) -> int: return n  # int\nprint(café(7))\n".encode()
        source = source.replace(b"\n", b"\r\n")
        result, functions, reason = widen.widen(source)
        self.assertEqual((functions, reason), (["café"], ""))
        self.assertEqual(result, source.replace(b"n: int) -> int:", b"n: Dynamic) -> Dynamic:"))

    def test_native_list_parameter_preserves_any_return_and_caller_storage(self):
        source = HEADER + (b"def expose(items: list[int]) -> Dynamic:\n    return items\n"
                           b"items: list[int] = [1]\nprint(expose(items) is items)\n")
        changed, functions, _ = widen.widen(source)
        self.assertEqual(functions, ["expose"])
        self.assertEqual(changed, source.replace(b"expose(items: list[int])", b"expose(items: Dynamic)"))

    def test_missing_native_list_fixture_fails_discovery(self):
        others = widen.PR_CASES - {widen.NATIVE_LIST_CASE}
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(widen.corpus, "programs", return_value=others):
            root = Path(directory)
            for case in others:
                path = root / case
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(HEADER + b"def f(n: int) -> int: return n\nprint(f(1))\n")
            with self.assertRaisesRegex(ValueError, widen.NATIVE_LIST_CASE):
                widen.discover(root)

    def test_non_targets_and_shadowed_names_stay_intact(self):
        fn = b"def f(n: int) -> int:\n    return n\nprint(f(2))\n"
        for payload in (b"@extern\n" + fn, b"int = UserType\n" + fn, fn + b"Dynamic = object\n",
                        fn + b"registered = f\n", fn + b"print(globals())\n",
                        b"from pkg import *\n" + fn, b"@registry.add\n" + fn,
                        fn.replace(b"return n", b"return (yield n)"),
                        fn.replace(b"int)", b"TypeVarT)"), fn.replace(b"int)", b"Iterator[int])"),
                        fn.replace(b"int)", b"ClassVar[int])"), fn.replace(b"int)", b"Final[int])"),
                        fn.replace(b"int)", b"InitVar[int])"), fn.replace(b"int)", b"KW_ONLY)"),
                        fn.replace(b"int)", b"list[str])"), fn.replace(b"int)", b"ffi.c_int)")):
            with self.subTest(source=payload):
                source = HEADER + payload
                self.assertEqual(widen.widen(source)[:2], (source, []))
        for source in (fn, b"\xef\xbb\xbf" + HEADER + fn, b"# coding: latin-1\n" + HEADER + fn):
            self.assertEqual(widen.widen(source)[:2], (source, []))

    def test_oracle_disagreement_blocks_every_native_lane(self):
        # Even a transformer mistake or indirect annotation observation cannot count as parity.
        case = "tests/programs/example/prog.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trees = (root / "original", root / "widened")
            for tree in trees:
                path = tree / case
                path.parent.mkdir(parents=True)
                path.write_bytes(b"original\n")
            with mock.patch.object(widen, "record", side_effect=[b"int\n[exit 0]\n", b"Any\n[exit 0]\n"]), \
                    mock.patch.object(widen.corpus, "run") as native, \
                    self.assertRaisesRegex(ValueError, "changed CPython output"):
                widen.execute(case, b"widened\n", trees, root, "compiler", {}, 1)
            native.assert_not_called()
            self.assertEqual((trees[1] / case).read_bytes(), b"original\n")
            (trees[1] / case).unlink()
            (trees[1] / case).symlink_to(trees[0] / case)
            with self.assertRaisesRegex(ValueError, "symlink"):
                widen.execute(case, b"widened\n", trees, root, "compiler", {}, 1)
            self.assertEqual((trees[0] / case).read_bytes(), b"original\n")

    def test_shard_union_and_fail_closed_evidence(self):
        candidates = {p: (b"", ["test_func"]) for p in widen.PR_CASES | {"an-extra-case"}}
        shards = [widen.selected_cases(candidates, "full", i, 2) for i in range(2)]
        self.assertFalse(set(shards[0]) & set(shards[1]))
        self.assertEqual(sorted(shards[0] + shards[1]), sorted(candidates))
        with mock.patch.object(widen, "discover", return_value=(candidates, {})), \
                mock.patch.object(widen.corpus, "exceptions", return_value={}):
            report = widen.expected_ci_report(widen.ROOT, "pr")
            widen.validate_report(report, widen.ROOT, "pr")
            for alter in (lambda r: r["cases"].pop(), lambda r: r["cases"][0]["results"].pop(),
                          lambda r: r["cases"][-1]["results"][-1].update(gc=1),
                          lambda r: r["cases"][-1]["results"][-1].update(result="expected-failure"),
                          lambda r: r["cases"][-1]["results"][-1].update(mode="jit"),
                          lambda r: r.update(failures=["CPython recording changed"])):
                broken = copy.deepcopy(report)
                alter(broken)
                with self.assertRaises(ValueError):
                    widen.validate_report(broken, widen.ROOT, "pr")


if __name__ == "__main__":
    unittest.main()
