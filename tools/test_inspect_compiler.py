"""Black-box inspection contracts: real compilation, immutable snapshots and isolation."""
import hashlib
import json
import re
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "inspect_compiler.py"
LOOP = """def total(values: list[int]) -> int:
    result = 0
    for value in values:
        result += value
    return result

print(total([1, 2, 3]))
"""


class InspectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("PYSTACHY_")}
        self.env["PYSTACHY_IRCHECK"] = "1"
        self.env["PYSTACHY_HOME"] = str(ROOT)

    def source(self, text, name="program.py"):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def inspect(self, path, output="report", args=(), env=None):
        destination = self.directory / output
        completed = subprocess.run(
            [sys.executable, str(TOOL), str(path), "--output", str(destination), *args],
            cwd=ROOT, env=self.env if env is None else env, capture_output=True,
            text=True, timeout=40,
        )
        return completed, destination

    def ordinary_ir(self, path, env=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "pystachy.py"), "ir", str(path)],
            cwd=ROOT, env=self.env if env is None else env, capture_output=True,
            timeout=40,
        )

    def report(self, destination):
        return json.loads((destination / "report.json").read_text(encoding="utf-8"))

    def snapshot(self, destination, stage):
        return json.loads((destination / f"{stage}.json").read_text(encoding="utf-8"))

    @staticmethod
    def operations(function):
        return function["slots"] + [operation for block in function["blocks"]
                                    for operation in block["operations"]]

    def named_function(self, snapshot, name):
        functions = [function for function in snapshot["functions"] if function["name"] == name]
        self.assertEqual(len(functions), 1, [function["name"] for function in snapshot["functions"]])
        return functions[0]

    def test_observation_preserves_exact_llvm_and_does_not_execute_program(self):
        marker = self.directory / "must-not-exist.txt"
        program = self.source(LOOP + f"with open({str(marker)!r}, 'w') as stream:\n    stream.write('ran')\n")
        ordinary = self.ordinary_ir(program)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        completed, destination = self.inspect(program)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(marker.exists(), "inspection executed the submitted program")
        self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)
        self.assertTrue((destination / "typed-before.json").is_file())
        self.assertTrue((destination / "typed-after.json").is_file())
        report = self.report(destination)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["diagnostics"], [])
        self.assertTrue(report["compiler"]["hosted"])
        self.assertTrue(report["verification"]["requested"])
        self.assertTrue(report["verification"]["completed"])
        self.assertGreater(report["verification"]["calls"], 0)
        self.assertEqual(report["input"]["sha256"], hashlib.sha256(program.read_bytes()).hexdigest())
        boundary = report["attempts"][-1]["dynamic_boundary"]
        self.assertFalse(boundary["dynamic_any_enabled"])
        self.assertEqual(boundary["tracked_modules"], [])
        self.assertIsNone(boundary["fallback_reason"])
        for footprint in boundary["footprints"].values():
            self.assertEqual(footprint["status"], "completed")
            self.assertEqual(footprint["totals"]["dynamic_operations"], {})
            self.assertEqual(footprint["totals"]["dynamic_runtime_calls"], {})
            self.assertEqual(footprint["totals"]["numeric_companion_slots"], 0)
            self.assertEqual(footprint["totals"]["numeric_generation_slots"], 0)

    def test_typed_after_only_skips_pass_records_not_the_final_snapshot(self):
        # The Lean corpus check's mode: the same LLVM, typed-after snapshot and descriptor
        # table, without the typed-before snapshot, pass records or diffs.
        program = self.source("# pystachy: dynamic-any\nfrom typing import Any\n" + LOOP
                              + "x: Any = 2.5\nif isinstance(x, float):\n    print(x + 1.0)\n")
        full, complete = self.inspect(program, "complete")
        self.assertEqual(full.returncode, 0, full.stderr)
        light, quick = self.inspect(program, "quick", ("--typed-after-only",))
        self.assertEqual(light.returncode, 0, light.stderr)
        self.assertEqual(self.snapshot(quick, "typed-after"), self.snapshot(complete, "typed-after"))
        self.assertTrue(self.snapshot(quick, "typed-after")["dynamic_types"] is not None)
        self.assertEqual((quick / "llvm.ll").read_bytes(), (complete / "llvm.ll").read_bytes())
        self.assertFalse((quick / "typed-before.json").exists())
        self.assertFalse((quick / "passes").exists() or (quick / "program-passes").exists())
        report, reference = self.report(quick), self.report(complete)
        self.assertEqual((report["status"], report["passes"], report["program_passes"]), ("ok", [], []))
        self.assertGreater(len(reference["passes"]), 0)
        self.assertEqual((report["settings"]["captures"], reference["settings"]["captures"]), ("typed-after", "all"))
        self.assertEqual([stage["status"] for stage in report["stages"]], ["skipped", "completed", "completed"])
        self.assertEqual(report["attempts"][-1]["dynamic_boundary"], reference["attempts"][-1]["dynamic_boundary"])

    def test_guard_evidence_keeps_nullcheck_inputs_but_typed_after_only_records_no_passes(self):
        # (the Lean report's mode: each nullcheck's input and output are in the snapshot)
        program = self.source(LOOP)
        full, complete = self.inspect(program, "complete", ("--guard-evidence",))
        self.assertEqual(full.returncode, 0, full.stderr)
        light, quick = self.inspect(program, "quick", ("--typed-after-only", "--guard-evidence"))
        self.assertEqual(light.returncode, 0, light.stderr)
        snapshot = self.snapshot(quick, "typed-after")
        self.assertEqual(snapshot, self.snapshot(complete, "typed-after"))
        self.assertGreater(len(snapshot["nullcheck_evidence"]), 0)
        self.assertFalse((quick / "passes").exists())
        self.assertEqual(self.report(quick)["passes"], [])
        self.assertTrue(any(item["name"] == "nullcheck" for item in self.report(complete)["passes"]))

    def test_dynamic_boundary_records_transitive_graph_outside_snapshot_filter(self):
        self.source("def number(text: str) -> int:\n    return int(text)\n", "boundary_leaf.py")
        self.source("import boundary_leaf\ndef number(text: str) -> int:\n"
                    "    return boundary_leaf.number(text)\n", "boundary_middle.py")
        self.source("# pystachy: dynamic-any\nfrom typing import Any\nimport boundary_middle\n"
                    "def make(text: str) -> Any:\n    value = boundary_middle.number(text)\n"
                    "    return value\n", "boundary_dynamic.py")
        program = self.source("import boundary_dynamic\ndef ordinary(text: str) -> str:\n"
                              "    return text\nprint(ordinary('x'), boundary_dynamic.make('1000'))\n")
        ordinary = self.ordinary_ir(program)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        completed, destination = self.inspect(program, args=("--function", "ordinary"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)
        attempt = self.report(destination)["attempts"][-1]
        boundary = attempt["dynamic_boundary"]
        modules = {module["name"]: module for module in boundary["modules"]}
        self.assertEqual(boundary["policy_status"], "observed")
        self.assertTrue(modules["boundary_dynamic"]["dynamic_any"])
        self.assertFalse(modules[""]["dynamic_any"])
        self.assertFalse(modules[""]["tracks_numeric_identity"])
        self.assertIn("boundary_middle", modules["boundary_dynamic"]["dependencies"])
        self.assertIn("boundary_leaf", modules["boundary_middle"]["dependencies"])
        for name in ("boundary_dynamic", "boundary_middle", "boundary_leaf"):
            self.assertTrue(modules[name]["tracks_numeric_identity"])
        for stage in ("before", "after"):
            footprint = boundary["footprints"][stage]
            self.assertEqual(footprint["status"], "completed")
            self.assertGreater(footprint["totals"]["functions"], attempt["selected_functions"])
            self.assertGreater(footprint["totals"]["numeric_companion_slots"], 0)
            self.assertGreater(footprint["totals"]["numeric_generation_slots"], 0)
            self.assertTrue(footprint["totals"]["dynamic_runtime_calls"])
            self.assertEqual(len(self.snapshot(destination, "typed-" + stage)["functions"]), 1)

    def test_boundary_hints_record_active_discarded_and_overridden_policies(self):
        safe = "def observe(text: str) -> str:\n    return text\n"
        unsafe = ("def observe(text: str) -> bool:\n    value = float(text)\n"
                  "    values = [value]\n    return value in values\n")
        program = self.source("# pystachy: dynamic-any\nimport boundary_inert\n"
                              "print(boundary_inert.observe('nan'))\n")
        for label, source in (("active", safe), ("discarded", unsafe),
                              ("overridden", "# pystachy: python-int\n" + safe)):
            with self.subTest(label=label):
                self.source("# pystachy: identity-inert\n" + source, "boundary_inert.py")
                ordinary = self.ordinary_ir(program)
                self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
                completed, destination = self.inspect(program, output=label)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)
                attempts = self.report(destination)["attempts"]
                first, final = [attempt["dynamic_boundary"] for attempt in (attempts[0], attempts[-1])]
                module = next(item for item in final["modules"] if item["name"] == "boundary_inert")
                self.assertTrue(module["identity_inert_requested"])
                self.assertEqual(module["identity_inert_active"], label == "active")
                self.assertEqual(module["promoting_int"], label == "overridden")
                self.assertFalse(final["full_graph_fallback"])
                if label == "discarded":
                    self.assertEqual(first["fallback_reason"], "numeric list in an identity-inert module")
                    self.assertFalse(final["hints_enabled"])
                    self.assertEqual(attempts[0]["status"], "retry")
                    for footprint in first["footprints"].values():
                        self.assertEqual(footprint["status"], "unavailable")
                        self.assertIsNone(footprint["totals"])
                else:
                    self.assertIsNone(first["fallback_reason"])

    def test_typed_toml_callback_reports_actual_full_graph_fallback(self):
        program = self.source("import tomllib\ndef parse_float(text: str) -> float:\n"
                              "    value = float(text)\n    return value\n"
                              "print(tomllib.loads('value = 1.5', parse_float=parse_float))\n")
        ordinary = self.ordinary_ir(program)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        completed, destination = self.inspect(program, args=("--function", "no_matching_function"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)
        attempts = self.report(destination)["attempts"]
        self.assertTrue(any(attempt["dynamic_boundary"]["fallback_reason"] == "number as an Any value"
                            for attempt in attempts))
        initial, final = [attempt["dynamic_boundary"] for attempt in (attempts[0], attempts[-1])]
        self.assertFalse(next(m for m in initial["modules"] if m["name"] == "")["tracks_numeric_identity"])
        self.assertTrue(final["full_graph_fallback"])
        self.assertTrue(all(module["tracks_numeric_identity"] for module in final["modules"]))
        self.assertFalse(next(m for m in final["modules"] if m["name"] == "")["dynamic_any"])
        self.assertTrue(any(m["dynamic_any"] and m["name"].startswith("tomllib") for m in final["modules"]))
        self.assertEqual(attempts[-1]["selected_functions"], 0)
        for footprint in final["footprints"].values():
            self.assertEqual(footprint["status"], "completed")
            self.assertGreater(footprint["totals"]["functions"], 0)
            self.assertGreater(footprint["totals"]["numeric_companion_slots"], 0)

    def test_library_intrinsics_keep_exact_llvm_when_observed(self):
        # The imported range adapter needs Loader's library-primitive parse context.
        # An observer must forward it as well as recording the source bytes.
        program = self.source("value = range(2, 11, 3)\nprint(len(value), value[1])\n")
        ordinary = self.ordinary_ir(program)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        completed, destination = self.inspect(program)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)
        self.assertEqual(self.report(destination)["status"], "ok")

    def test_failed_lowering_keeps_boundary_footprints_partial(self):
        program = self.source(LOOP)
        destination = self.directory / "partial"
        destination.mkdir()
        script = '''
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / "tools"))
import inspect_compiler
from src.pystachy_compiler.gen import Gen
def stopped_lowering(gen, fn):
    raise RuntimeError("test stops lowering after typed IR capture")
Gen.lower = stopped_lowering
raise SystemExit(inspect_compiler.worker(argparse.Namespace(
    source=sys.argv[1], output=sys.argv[2], function="no_matching_function")))
'''
        completed = subprocess.run([sys.executable, "-c", script, str(program), str(destination)],
                                   cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=40)
        self.assertEqual(completed.returncode, 2, completed.stderr)
        report = self.report(destination)
        self.assertEqual(report["status"], "error")
        attempt = report["attempts"][-1]
        self.assertEqual(attempt["status"], "failed")
        for footprint in attempt["dynamic_boundary"]["footprints"].values():
            self.assertEqual(footprint["status"], "partial")
            self.assertGreater(footprint["totals"]["functions"], 0)

    def test_same_operation_count_rewrite_has_immutable_snapshots_and_real_diff(self):
        program = self.source(LOOP)
        completed, destination = self.inspect(program, args=("--function", "total"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        before = self.named_function(self.snapshot(destination, "typed-before"), "total")
        after = self.named_function(self.snapshot(destination, "typed-after"), "total")
        self.assertTrue(any(op["op"] == "rt" and op["text"] == "list.get"
                            for op in self.operations(before)))
        self.assertTrue(any(op["op"] == "list.load" for op in self.operations(after)))
        self.assertFalse(any(op["op"] == "list.load" for op in self.operations(before)),
                         "the before snapshot retained mutable IR objects")
        self.assertEqual(before["location"], {"file": str(program), "line": 1,
                                             "column": None, "precision": "function"})
        self.assertEqual(before["parameters"][0]["type"], "list[int]")
        self.assertEqual(before["return_type"], "int")
        rewritten = [item for item in self.report(destination)["passes"]
                     if item["name"] == "listget" and item["function"] == before["symbol"]]
        self.assertEqual(len(rewritten), 1)
        event = rewritten[0]
        self.assertTrue(event["changed"])
        self.assertEqual(event["reported_rewrites"], 1)
        self.assertEqual(sum(event["before_operations"].values()),
                         sum(event["after_operations"].values()))
        diff = (destination / event["diff"]).read_text(encoding="utf-8")
        self.assertIn("list.get", diff)
        self.assertIn("list.load", diff)

    def test_disabling_all_passes_still_captures_verified_typed_ir(self):
        program = self.source(LOOP)
        env = dict(self.env, PYSTACHY_OPT="-all")
        completed, destination = self.inspect(program, args=("--function", "total"), env=env)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        before = self.named_function(self.snapshot(destination, "typed-before"), "total")
        after = self.named_function(self.snapshot(destination, "typed-after"), "total")
        self.assertTrue(any(op["op"] == "rt" and op["text"] == "list.get"
                            for op in self.operations(after)))
        # The depth policy is no optimization: it still runs, and drops only the entry-depth
        # snapshot of this function, which neither recurses nor has a handler.
        before_ops = [op for op in self.operations(before) if op["text"] != "recursion.depth"]
        self.assertEqual(before_ops, self.operations(after))
        self.assertEqual([event["name"] for event in self.report(destination)["program_passes"]], ["recursionscope"])
        passes = self.report(destination)["passes"]
        self.assertFalse(any(event["name"] in {"charslots", "listget", "listguard", "dictfuse", "unionslots", "nullcheck"}
                             for event in passes), "disabled pass was reported as executed")
        ordinary = self.ordinary_ir(program, env=env)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)

    def test_recursion_policy_pass_reports_counted_functions_by_symbol(self):
        program = self.source('''
def leaf(n: int) -> int:
    return n + 1
def recursive(n: int) -> int:
    if n <= 0:
        return 0
    return recursive(n - 1) + leaf(n)
def kernel(n: int) -> int:
    total = 0
    for i in range(n):
        total += leaf(i) + recursive(i)
    return total
print(kernel(3))
''')
        ordinary = self.ordinary_ir(program)
        completed, destination = self.inspect(program, args=("--function", "kernel"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)
        report = self.report(destination)
        events = {event["name"]: event for event in report["program_passes"]}
        self.assertEqual(set(events), {"recursionscope"})
        event = events["recursionscope"]
        self.assertEqual(event["return_unit"], "counted source functions")
        self.assertEqual(event["reported_transformations"], 1)
        self.assertEqual(event["added_functions"], [])
        self.assertEqual(event["removed_functions"], [])
        self.assertFalse(event["order_changed"])
        self.assertIn("@f.recursive", event["changed_functions"])
        self.assertIn("@f.kernel", event["changed_functions"])
        snapshots = json.loads((destination / event["snapshot"]).read_text())
        before, after = snapshots["before"], snapshots["after"]
        for snapshot in (before, after):
            totals = snapshot["totals"]
            self.assertEqual(totals["slots"], sum(fn["slots"] for fn in snapshot["functions"].values()))
            self.assertEqual(totals["operation_count"], sum(totals["operations"].values()))
            self.assertEqual(set(totals["guards"]), {"enter", "resume", "leave", "depth", "restore"})
        for name in ("@f.leaf", "@f.recursive", "@f.kernel"):
            self.assertTrue(before["functions"][name]["recursion"]["counted"], name)
            self.assertEqual(before["functions"][name]["guards"]["depth"], 1, name)
        self.assertTrue(after["functions"]["@f.recursive"]["recursion"]["counted"])
        self.assertEqual(after["functions"]["@f.recursive"]["guards"]["enter"], 1)
        # (it calls only itself and leaf: closed recursion, whose depth lowering passes along)
        self.assertTrue(after["functions"]["@f.recursive"]["recursion"]["closed"])
        self.assertFalse(before["functions"]["@f.recursive"]["recursion"]["closed"])
        self.assertEqual(after["functions"]["@f.recursive"]["guards"]["restore"], 0)
        for name in ("@f.leaf", "@f.kernel"):
            self.assertFalse(after["functions"][name]["recursion"]["counted"], name)
            self.assertEqual(sum(after["functions"][name]["guards"].values()), 0, name)
        self.assertIn("@f.kernel", before["selected_snapshots"])
        self.assertNotIn("@f.leaf", before["selected_snapshots"])
        self.assertTrue((destination / event["diff"]).is_file())

    def test_zero_program_result_does_not_invent_refusal(self):
        program = self.source("stream = open('never-opened-for-observation')\nstream.close()\n")
        completed, destination = self.inspect(program, args=("--function", "no_such_function"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = self.report(destination)
        self.assertEqual(len(report["program_passes"]), 1)
        for event in report["program_passes"]:
            self.assertEqual(event["reported_transformations"], 0)
            self.assertEqual(event["before_selected_totals"]["functions"], 0)
            self.assertGreater(event["before_totals"]["functions"], 0)
            self.assertNotIn("refusal_reason", event)
            self.assertIn("zero does not identify", event["explanation_scope"])
        ordinary = self.ordinary_ir(program)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)

    def test_recursive_requests_share_identity_only_for_matching_layouts(self):
        program = ROOT / "tests/programs/generics/generic_distinct_layouts.py"
        completed, destination = self.inspect(program, args=("--function", "no_such_function"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = self.report(destination)
        selected = report["attempts"][-1]["class_specializations"]
        layouts = {cls["fields"]["values"]: (identity, cls) for identity, cls in selected.items()
                   if cls["template"] == "Collection"}
        self.assertEqual(set(layouts), {"list[int]", "tuple[int,int]"})
        identity, native_list = layouts["list[int]"]
        self.assertEqual(native_list["fields"]["next"], identity)
        self.assertEqual(native_list["bindings"], {"T": "int"})
        self.assertEqual(layouts["tuple[int,int]"][1]["bindings"], native_list["bindings"])
        self.assertCountEqual(native_list["request_keys"],
                              ["Collection(list[int])", "Collection[);T=int", "Collection<list[int]>;T=int"])
        self.assertEqual(set(report["pass_contracts"]), {"charslots", "listget", "listguard", "dictfuse", "unionslots", "nullcheck"})
        self.assertIn("read-effect-bounds", report["pass_contracts"]["unionslots"]["invalidates"])

    def test_rejected_class_is_explained_without_publishing_its_tentative_key(self):
        program = self.source("class Kept:\n    def __init__(self, value):\n        self.value = value\n"
                              "class Broken:\n    def __init__(self, value):\n        self.value = missing\n"
                              "x = Kept('yes')\ny = Broken(1)\n")
        ordinary = self.ordinary_ir(program)
        completed, destination = self.inspect(program)
        self.assertEqual((ordinary.returncode, completed.returncode), (1, 1))
        self.assertEqual((destination / "compiler.stderr").read_bytes(), ordinary.stderr)
        report = self.report(destination)
        self.assertIn("specializing Broken(int)", report["diagnostics"][0]["context"][-1])
        attempt = report["attempts"][-1]
        self.assertEqual(attempt["status"], "failed")
        self.assertEqual([cls["template"] for cls in attempt["class_specializations"].values()], ["Kept"])

    def test_semantic_rejection_links_imported_specialization_without_parsing_paths(self):
        support = self.source("def add(value):\n    return value + 'x'\n", "folder:é/worker_support.py")
        program = self.source("import worker_support\nprint(worker_support.add(1))\n", "folder:é/program.py")
        syntax_only = subprocess.run(
            [sys.executable, str(ROOT / "pystachy.py"), "check", str(program)],
            cwd=ROOT, env=self.env, capture_output=True, timeout=40,
        )
        self.assertEqual(syntax_only.returncode, 0, syntax_only.stderr)
        completed, destination = self.inspect(program)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        report = self.report(destination)
        self.assertEqual(report["status"], "rejected")
        self.assertFalse(report["verification"]["completed"])
        self.assertEqual(len(report["diagnostics"]), 1)
        diagnostic = report["diagnostics"][0]
        self.assertEqual(diagnostic["code"], "PYS0001")
        self.assertEqual(diagnostic["phase"], "semantic")
        self.assertEqual(diagnostic["file"], str(support))
        self.assertEqual(diagnostic["line"], 2)
        self.assertIsNone(diagnostic["column"])
        self.assertIn("unsupported operand", diagnostic["message"])
        self.assertTrue(any("add(int)" in context for context in diagnostic["context"]))
        self.assertFalse((destination / "llvm.ll").exists())
        self.assertTrue(all(stage["status"] == "unavailable" for stage in report["stages"]))

    def test_syntax_failure_is_not_reported_as_semantic_or_verified(self):
        program = self.source("def broken(:\n    pass\n")
        completed, destination = self.inspect(program)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        report = self.report(destination)
        self.assertEqual(report["status"], "rejected")
        self.assertFalse(report["verification"]["completed"])
        self.assertEqual(report["diagnostics"][0]["phase"], "parse")
        self.assertEqual(report["diagnostics"][0]["file"], str(program))
        self.assertEqual(report["diagnostics"][0]["line"], 1)
        self.assertFalse((destination / "llvm.ll").exists())

    def test_function_filter_does_not_suppress_other_compile_errors(self):
        program = self.source(LOOP + "\ndef unrelated(value: int) -> int:\n    return value + 'x'\n")
        completed, destination = self.inspect(program, args=("--function", "total"))
        self.assertEqual(completed.returncode, 1, completed.stderr)
        report = self.report(destination)
        self.assertEqual(report["status"], "rejected")
        self.assertIn("unsupported operand", report["diagnostics"][0]["message"])
        self.assertFalse((destination / "llvm.ll").exists())

    def test_retries_are_observed_without_transient_diagnostics_or_duplicate_functions(self):
        program = self.source("# pystachy: dynamic-any\nclass Box:\n"
                              "    def __init__(self, payload):\n        self.payload = payload\n"
                              "def pick(flag: bool):\n"
                              "    value = 300\n    if flag:\n        value = 2.5\n"
                              "    return Box(value)\nprint(pick(True).payload)\n")
        completed, destination = self.inspect(program, args=("--function", "pick"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = self.report(destination)
        self.assertEqual(report["diagnostics"], [])
        self.assertGreaterEqual(len(report["attempts"]), 2)
        self.assertTrue(any(attempt["status"] == "retry" for attempt in report["attempts"]))
        self.assertEqual(report["attempts"][-1]["status"], "completed")
        earlier, final = (attempt["class_specializations"] for attempt in
                          (report["attempts"][0], report["attempts"][-1]))
        self.assertEqual(set(earlier), set(final))
        identity, = earlier
        self.assertEqual(earlier[identity]["fields"], {"payload": "int"})
        self.assertEqual(final[identity]["fields"], {"payload": "union[float,int]"})
        self.named_function(self.snapshot(destination, "typed-before"), "pick")
        self.named_function(self.snapshot(destination, "typed-after"), "pick")
        ordinary = self.ordinary_ir(program)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)

    def test_dynamic_types_match_the_emitted_descriptors(self):
        program = self.source("# pystachy: dynamic-any\nfrom typing import Any\n"
                              "class Base:\n    pass\nclass Sub(Base):\n    pass\n"
                              "def name(x: Any) -> str:\n    return type(x).__name__\n"
                              "def call(f: Any) -> Any:\n    return f()\n"
                              "print(name(Base()), name(Sub()), call(lambda: 1))\n")
        completed, destination = self.inspect(program)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        types = {entry["symbol"]: entry for entry in self.snapshot(destination, "typed-after")["dynamic_types"]}
        self.assertEqual(types["@dt.Sub"]["base"], "@dt.Base")
        self.assertEqual((types["@dt.Base"]["payload"], types["@dt.Sub"]["payload"]), ("Base", "Sub"))
        self.assertNotEqual(types["@dt.Base"]["cls"], types["@dt.Sub"]["cls"])
        self.assertTrue(any(entry["kind"] == 9 and entry["payload"].startswith("fn[") for entry in types.values()))
        # Each entry's kind, class number, base and flags are those of the descriptor in the LLVM.
        emitted = {}
        for line in (destination / "llvm.ll").read_text().splitlines():
            found = re.match(r"(@dtf?\.\S+) = internal constant .*?\{i64 (-?\d+), ptr [^,]+, ptr [^,]+, "
                             r"i64 (-?\d+), ptr ([^,]+), i64 (-?\d+),", line)
            if found:
                symbol, kind, cls, base, flags = found.groups()
                emitted[symbol] = (int(kind), int(cls), "" if base == "null" else base, int(flags))
        self.assertEqual(emitted, {symbol: (entry["kind"], entry["cls"], entry["base"], entry["flags"])
                                   for symbol, entry in types.items()})

    def test_repaired_import_uses_current_bytes_and_no_prior_failure_state(self):
        support = self.source("def add(value):\n    return value + 'x'\n", "worker_support.py")
        program = self.source("import worker_support\nprint(worker_support.add(1))\n")
        failed, failure_dir = self.inspect(program, output="failed")
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertEqual(self.report(failure_dir)["status"], "rejected")
        support.write_text("def add(value):\n    return value + 2\n", encoding="utf-8")
        completed, destination = self.inspect(program, output="repaired")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = self.report(destination)
        self.assertEqual(report["diagnostics"], [])
        self.assertEqual(report["status"], "ok")
        modules = {item["path"]: item["sha256"] for item in report["input"]["modules"]}
        self.assertEqual(modules[str(support)], hashlib.sha256(support.read_bytes()).hexdigest())
        ordinary = self.ordinary_ir(program)
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)

    def test_timeout_is_distinct_from_rejection_and_has_no_success_artifact(self):
        program = self.source(LOOP)
        completed, destination = self.inspect(program, args=("--timeout", "0.000001"))
        self.assertEqual(completed.returncode, 124, completed.stderr)
        report = self.report(destination)
        self.assertEqual(report["status"], "timeout")
        self.assertFalse(report["verification"]["completed"])
        self.assertFalse((destination / "llvm.ll").exists())

    def test_invalid_timeout_fails_before_creating_artifacts(self):
        program = self.source(LOOP)
        for index, invalid in enumerate(("0", "-1", "nan", "inf")):
            with self.subTest(timeout=invalid):
                completed, destination = self.inspect(program, output=f"invalid-{index}",
                                                      args=("--timeout", invalid))
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertFalse(destination.exists())

    def test_missing_input_is_setup_failure_not_program_rejection(self):
        program = self.directory / "missing.py"
        completed, destination = self.inspect(program)
        self.assertEqual(completed.returncode, 2, completed.stderr)
        report = self.report(destination)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["attempts"], [])
        self.assertEqual(report["diagnostics"][0]["phase"], "input")
        self.assertFalse(report["verification"]["completed"])
        self.assertFalse((destination / "llvm.ll").exists())

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "killpg"), "requires POSIX FIFOs")
    def test_fifo_input_cannot_block_error_or_timeout_reporting(self):
        source = self.directory / "source.py"
        os.mkfifo(source)
        # Keep temporary staging owned by this test even when the negative
        # control is killed before TemporaryDirectory can clean itself up.
        env = dict(self.env, TMPDIR=str(self.directory))
        for name, timeout, expected_code, expected_status in (
            ("nonregular", "5", 2, "error"),
            ("expired", "0.000001", 124, "timeout"),
        ):
            with self.subTest(status=expected_status):
                destination = self.directory / name
                process = subprocess.Popen(
                    [sys.executable, str(TOOL), str(source), "--output", str(destination),
                     "--timeout", timeout], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, start_new_session=True,
                )
                try:
                    _, stderr = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.communicate(timeout=5)
                    self.fail("FIFO blocked the CLI beyond its worker deadline")
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate(timeout=5)
                self.assertEqual(process.returncode, expected_code, stderr)
                report = self.report(destination)
                self.assertEqual(report["status"], expected_status)
                self.assertIsNone(report["input"]["sha256"])
                self.assertFalse(report["verification"]["completed"])
                self.assertTrue(all(stage["status"] == "unavailable" for stage in report["stages"]))
                self.assertFalse((destination / "llvm.ll").exists())
                if expected_status == "error":
                    self.assertEqual(report["diagnostics"][0]["code"], "PYS9001")
                    self.assertEqual(report["diagnostics"][0]["phase"], "input")
                    self.assertIn("regular file", report["diagnostics"][0]["message"])
                    self.assertEqual(report["attempts"], [])
        regular = self.source(LOOP, "regular.py")
        linked = self.directory / "linked.py"
        linked.symlink_to(regular)
        completed, destination = self.inspect(linked, output="linked-report")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.report(destination)["input"]["sha256"],
                         hashlib.sha256(regular.read_bytes()).hexdigest())

    def test_output_and_missing_parent_do_not_create_imports_during_observation(self):
        # Creating the destination before compiling turns an absent module into
        # a namespace package and flips the program's optional-import branch.
        for output in ("inspection_out", "inspection_out/nested/report"):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary) / "program.py"
                source.write_text("try:\n    import inspection_out\n    print('present')\n"
                                  "except ImportError:\n    print('missing')\n", encoding="utf-8")
                ordinary = self.ordinary_ir(source)
                self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
                self.assertIn(b"missing", ordinary.stdout)
                destination = Path(temporary) / output
                completed = subprocess.run(
                    [sys.executable, str(TOOL), str(source), "--output", str(destination)],
                    cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=40,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual((destination / "llvm.ll").read_bytes(), ordinary.stdout)

    def test_changed_import_cannot_certify_bytes_that_were_not_compiled(self):
        support = self.source("value = 111\n", "worker_support.py")
        program = self.source("import worker_support\nprint(worker_support.value)\n")
        destination = self.directory / "changed"
        destination.mkdir()
        script = '''
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / "tools"))
import inspect_compiler
from src.pystachy_compiler.gen import Gen
source, output, dependency = sys.argv[1:]
original_program = Gen.program
def change_loaded_input(gen, modules):
    Path(dependency).write_text("value = 222\\n", encoding="utf-8")
    return original_program(gen, modules)
Gen.program = change_loaded_input
raise SystemExit(inspect_compiler.worker(argparse.Namespace(
    source=source, output=output, function="")))
'''
        completed = subprocess.run(
            [sys.executable, "-c", script, str(program), str(destination), str(support)],
            cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=40,
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        report = self.report(destination)
        self.assertEqual(report["status"], "error")
        self.assertTrue(report["input"]["changed_during_compilation"])
        self.assertFalse(report["verification"]["completed"])
        self.assertTrue(any(diagnostic["code"] == "PYS9003" for diagnostic in report["diagnostics"]))
        reads = [item for item in report["input"]["modules"] if item["path"] == str(support)]
        self.assertTrue(reads)
        expected = hashlib.sha256(b"value = 111\n").hexdigest()
        self.assertTrue(any(item["source_sha256"] == expected for item in reads))
        self.assertTrue(any(item["changed_since_read"] for item in reads))
        self.assertTrue(all(stage["status"] != "completed" for stage in report["stages"]))
        for attempt in report["attempts"]:
            boundary = attempt["dynamic_boundary"]
            self.assertEqual(boundary["source_provenance"], "inconsistent")
            self.assertTrue(all(footprint["status"] != "completed" for footprint in boundary["footprints"].values()))

    def test_crlf_source_hashes_distinguish_raw_bytes_from_consumed_text(self):
        program = self.source(LOOP)
        raw = LOOP.replace("\n", "\r\n").encode("utf-8")
        program.write_bytes(raw)
        completed, destination = self.inspect(program)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = self.report(destination)
        self.assertFalse(report["input"]["changed_during_compilation"])
        reads = [item for item in report["input"]["modules"] if item["path"] == str(program)]
        self.assertTrue(reads)
        for item in reads:
            self.assertEqual(item["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(item["source_sha256"], hashlib.sha256(LOOP.encode("utf-8")).hexdigest())
            self.assertFalse(item["changed_since_read"])

    def test_existing_output_is_preserved_including_stale_success_artifacts(self):
        program = self.source("missing_name\n")
        destination = self.directory / "report"
        destination.mkdir()
        old_report = b'{"status": "old-success"}\n'
        (destination / "report.json").write_bytes(old_report)
        old_ir = b"previous LLVM, must not masquerade as this run\n"
        (destination / "llvm.ll").write_bytes(old_ir)
        completed, _ = self.inspect(program)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual((destination / "report.json").read_bytes(), old_report)
        self.assertEqual((destination / "llvm.ll").read_bytes(), old_ir)
        self.assertEqual(program.read_text(encoding="utf-8"), "missing_name\n")

    def test_output_cannot_replace_source_file(self):
        program = self.source(LOOP)
        original = program.read_bytes()
        completed, _ = self.inspect(program, output=program.name)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(program.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
