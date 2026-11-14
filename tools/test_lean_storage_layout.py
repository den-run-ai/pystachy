"""Independent real-IR controls for tuple representation crossings."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_int
from check_lean_storage import DEFAULT_CHECKER, MIN, check_all


ROOT = Path(__file__).resolve().parent.parent
NARROW = "OverflowError: Python int too large to convert to C long"
CHECKERS_PRESENT = DEFAULT_CHECKER.is_file() and check_lean_int.DEFAULT_CHECKER.is_file()
if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not CHECKERS_PRESENT:
    raise RuntimeError("Lean storage and integer checkers are required; build tools/lean_boundary first")

FIXED = """def take(t: tuple[int, int]) -> int:
    return t[0] + t[1]


def take_nested(t: tuple[tuple[int, int], int]) -> int:
    return t[0][0] + t[0][1] + t[1]


def make(n: int) -> tuple[int, int]:
    return n, 1


def read_opt(t: tuple[int, int] | None) -> int:
    if t is None:
        return 0
    return t[0] + t[1]


def contains(xs: list[tuple[int, int]], t: tuple[int, int] | None) -> bool:
    return t in xs
"""
NARROW_PROGRAM = """# pystachy: python-int
import sys
from fixed import take
n = (len(sys.argv) + 1) * 2 ** 64
p = (n, n)
try:
    print(take(p))
except OverflowError:
    print('overflow')
"""
NESTED_PROGRAM = NARROW_PROGRAM.replace("import take", "import take_nested").replace(
    "p = (n, n)", "p = ((n, n), n)").replace("take(p)", "take_nested(p)")
WIDEN_PROGRAM = """# pystachy: python-int
import sys
from fixed import make
p = make(-9223372036854775808)
xs = [p]
print(xs[0][0] + len(sys.argv))
"""
OPTIONAL_PROGRAM = """# pystachy: python-int
import sys
from fixed import read_opt
n = (len(sys.argv) + 1) * 2 ** 64
d = {'a': (n, n)}
try:
    print(read_opt(d.get('a')))
except OverflowError:
    print('overflow')
"""
SEARCH_PROGRAM = """# pystachy: python-int
from fixed import contains
print(contains([(1, 2)], (1, 2)), contains([(1, 2)], None))
"""


def compile_snapshot(program, output, paths=()):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    environment["PYSTACHY_HOME"] = str(ROOT)
    if paths:
        environment["PYSTACHY_PATH"] = os.pathsep.join(str(path) for path in paths)
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program),
         "--output", str(output), "--typed-after-only"],
        cwd=ROOT, env=environment, text=True, capture_output=True, timeout=60)
    if completed.returncode:
        raise AssertionError(completed.stdout + completed.stderr)
    return json.loads((output / "typed-after.json").read_text())


def selected(snapshot, symbol):
    result = copy.deepcopy(snapshot)
    result["functions"] = [fn for fn in result["functions"] if fn["symbol"] == symbol]
    if len(result["functions"]) != 1:
        raise AssertionError("missing or ambiguous function: " + symbol)
    return result


@unittest.skipUnless(CHECKERS_PRESENT, "build tools/lean_boundary to run the proved checkers")
class StorageLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        (directory / "fixed.py").write_text(FIXED, encoding="utf-8")
        cls.snapshots = {}
        for name, text in (("narrow", NARROW_PROGRAM), ("nested", NESTED_PROGRAM),
                           ("widen", WIDEN_PROGRAM), ("optional", OPTIONAL_PROGRAM), ("search", SEARCH_PROGRAM)):
            program = directory / (name + ".py")
            program.write_text(text, encoding="utf-8")
            cls.snapshots[name] = compile_snapshot(program, directory / (name + "-snapshot"))
        for name, filename in (("dict-items", "python_int_dict_items.py"), ("dict-values", "python_int_dict_values.py")):
            cls.snapshots[name] = compile_snapshot(
                ROOT / "tests/programs/numbers" / filename, directory / (name + "-snapshot"),
                [ROOT / "tests/python_int_modules"])
        cls.snapshots["kwargs"] = compile_snapshot(
            ROOT / "tests/programs/classes/contextmanager_python_int_args.py", directory / "kwargs-snapshot")

    def assert_accepted(self, snapshot):
        report, code = check_all(snapshot)
        self.assertEqual((report["status"], code), ("accepted", 0), report)
        self.assertGreater(report["totals"]["obligations"], 0)

    def assert_rejected(self, snapshot, kind):
        report, code = check_all(snapshot)
        self.assertEqual((report["status"], code), ("rejected", 1), report)
        self.assertTrue(any(site["kind"] == kind for fn in report["functions"]
                            for site in fn.get("unproved", [])), report)

    def test_real_nested_and_mixed_container_baselines(self):
        for name, snapshot in self.snapshots.items():
            with self.subTest(program=name):
                self.assert_accepted(snapshot)
        # This actual corpus case deliberately mixes fixed and promoting items;
        # a test that silently switched all tuples to promoting would lose it.
        sources = [source for fn in self.snapshots["dict-items"]["functions"]
                   for source in fn["representation_metadata"]["sources"]]
        self.assertTrue(any(source["representation"] == "tuple[int+,int]" for source in sources))

    def test_all_nine_required_narrowing_guards_are_individually_rejected(self):
        count = 0
        cases = (("narrow", "@main.init", 2), ("nested", "@main.init", 3),
                 ("dict-items", "@f.fixed_dict_pairs$first", 2),
                 ("dict-values", "@f.fixed_dict_values$first_value", 2))
        for name, symbol, expected in cases:
            original = selected(self.snapshots[name], symbol)
            self.assert_accepted(original)
            sites = [(bi, oi) for bi, block in enumerate(original["functions"][0]["blocks"])
                     for oi, op in enumerate(block["operations"]) if op["op"] == "check" and op["text"] == NARROW]
            self.assertEqual(len(sites), expected, name)
            for bi, oi in sites:
                with self.subTest(program=name, block=bi, instruction=oi):
                    mutated = copy.deepcopy(original)
                    mutated["functions"][0]["blocks"][bi]["operations"][oi]["operands"][0]["value"] = "false"
                    self.assert_rejected(mutated, "narrowing")
                    count += 1
        self.assertEqual(count, 9)

    def test_skipping_decoder_marker_arm_cannot_manufacture_fit(self):
        original = selected(self.snapshots["narrow"], "@main.init")
        fn = original["functions"][0]
        definitions = {f"%t{result}": op for block in fn["blocks"]
                       for op in block["operations"] for result in op["results"]}
        sites = []
        for bi, block in enumerate(fn["blocks"]):
            for oi, op in enumerate(block["operations"]):
                if op["op"] == "cbr":
                    condition = definitions.get(op["operands"][0]["value"], {})
                    if condition.get("op") == "scalar.cmp" and any(
                            operand["value"] == MIN for operand in condition["operands"]):
                        sites.append((bi, oi))
        self.assertEqual(len(sites), 2)
        for bi, oi in sites:
            with self.subTest(block=bi, instruction=oi):
                mutated = copy.deepcopy(original)
                mutated["functions"][0]["blocks"][bi]["operations"][oi]["operands"][0]["value"] = "false"
                report, code = check_all(mutated)
                self.assertEqual((report["status"], code), ("rejected", 1), report)

    def test_plain_sentinel_requires_promoting_copy_guard(self):
        original = selected(self.snapshots["widen"], "@main.init")
        self.assert_accepted(original)
        fn = original["functions"][0]
        allocating = {block["label"] for block in fn["blocks"] if any(
            op["op"] == "alloc.fixed" and op["type"] == "tuple[int+,int+]" for op in block["operations"])}
        sites = [(bi, oi) for bi, block in enumerate(fn["blocks"]) for oi, op in enumerate(block["operations"])
                 if op["op"] == "cbr" and op["targets"][0] in allocating]
        self.assertEqual(len(sites), 1)
        bi, oi = sites[0]
        mutated = copy.deepcopy(original)
        mutated["functions"][0]["blocks"][bi]["operations"][oi]["operands"][0]["value"] = "false"
        self.assert_rejected(mutated, "promoting-view")

    def test_optional_tuple_crossing_requires_both_narrowing_checks(self):
        original = selected(self.snapshots["optional"], "@main.init")
        self.assert_accepted(original)
        sites = [(bi, oi) for bi, block in enumerate(original["functions"][0]["blocks"])
                 for oi, op in enumerate(block["operations"]) if op["op"] == "check" and op["text"] == NARROW]
        self.assertEqual(len(sites), 2)
        for bi, oi in sites:
            with self.subTest(block=bi, instruction=oi):
                mutated = copy.deepcopy(original)
                mutated["functions"][0]["blocks"][bi]["operations"][oi]["operands"][0]["value"] = "false"
                self.assert_rejected(mutated, "narrowing")

    def test_big_dictionary_key_requires_matching_digits(self):
        original = selected(self.snapshots["dict-items"], "@main.init")
        self.assert_accepted(original)
        mutated = copy.deepcopy(original)
        calls = [op for block in mutated["functions"][0]["blocks"] for op in block["operations"]
                 if op["op"] == "rt" and op["text"] == "dict.bkey_getbox"]
        self.assertEqual(len(calls), 1)
        # The original transfers both words; dropping digits silently changes a
        # large key into its zero low word and must not receive that exemption.
        calls[0]["operands"][2]["value"] = "null"
        self.assert_rejected(mutated, "low-word")

    def test_search_result_contract_does_not_justify_unguarded_input(self):
        original = selected(self.snapshots["search"], "@f.fixed$contains")
        self.assert_accepted(original)
        fn = original["functions"][0]
        contracts = [source for source in fn["representation_metadata"]["sources"]
                     if source["origin"] == "search_hold"]
        self.assertEqual(len(contracts), 1)
        allocating = {block["label"] for block in fn["blocks"] if any(
            op["op"] == "alloc.fixed" and op["type"] == "tuple[int+,int+]" for op in block["operations"])}
        sites = [(bi, oi) for bi, block in enumerate(fn["blocks"]) for oi, op in enumerate(block["operations"])
                 if op["op"] == "cbr" and op["targets"][0] in allocating]
        self.assertEqual(len(sites), 1)
        bi, oi = sites[0]
        mutated = copy.deepcopy(original)
        mutated["functions"][0]["blocks"][bi]["operations"][oi]["operands"][0]["value"] = "false"
        self.assert_rejected(mutated, "promoting-view")

    def kwargs_functions(self):
        snapshot = self.snapshots["kwargs"]
        functions = []
        for fn in snapshot["functions"]:
            decoded = {op["operands"][0]["value"] for block in fn["blocks"] for op in block["operations"]
                       if op["op"] == "tuple.load"}
            loads = [op for block in fn["blocks"] for op in block["operations"]
                     if op["op"] == "mem.load" and op["type"] == "kw[extra:int+]" and
                     f"%t{op['results'][-1]}" in decoded]
            if loads:
                self.assertEqual(len(loads), 1)
                functions.append((selected(snapshot, fn["symbol"]), loads[0]["results"][-1]))
        self.assertEqual(len(functions), 2)
        return functions

    def test_kwargs_load_contract_is_not_inferred_from_consuming_view(self):
        for original, result in self.kwargs_functions():
            self.assert_accepted(original)
            for typ, status, code in (("%ptr", "unsupported", 2), ("kw[extra:int]", "rejected", 1)):
                with self.subTest(function=original["functions"][0]["symbol"], producer=typ):
                    mutated = copy.deepcopy(original)
                    fn = mutated["functions"][0]
                    load = next(op for block in fn["blocks"] for op in block["operations"]
                                if op["results"] == [result])
                    load["type"] = typ
                    load["operands"][0]["type"] = "*" + typ
                    report, actual = check_all(mutated)
                    self.assertEqual((report["status"], actual), (status, code), report)
                    if status == "rejected":
                        self.assert_rejected(mutated, "promoting-view")

    def test_each_kwargs_tail_read_still_requires_its_marker_guard(self):
        for original, result in self.kwargs_functions():
            fn = original["functions"][0]
            definitions = {f"%t{r}": op for block in fn["blocks"]
                           for op in block["operations"] for r in op["results"]}
            sites = []
            for bi, block in enumerate(fn["blocks"]):
                for oi, op in enumerate(block["operations"]):
                    if op["op"] != "cbr":
                        continue
                    condition = definitions.get(op["operands"][0]["value"], {})
                    if condition.get("op") != "scalar.cmp" or condition["text"] != "eq":
                        continue
                    if not any(a["value"] == MIN for a in condition["operands"]):
                        continue
                    words = [definitions.get(a["value"], {}) for a in condition["operands"]]
                    if any(word.get("op") == "tuple.load" and word["immediate"] == 0 and word["operands"] ==
                           [{"value": f"%t{result}", "type": "tuple[int+]"}] for word in words):
                        sites.append((bi, oi))
            self.assertEqual(len(sites), 1, fn["symbol"])
            for bi, oi in sites:
                mutated = copy.deepcopy(original)
                mutated["functions"][0]["blocks"][bi]["operations"][oi]["operands"][0]["value"] = "true"
                self.assert_rejected(mutated, "tail-marker")


if __name__ == "__main__":
    unittest.main()
