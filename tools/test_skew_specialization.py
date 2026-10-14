"""Profile hints must preserve baseline typing and native call semantics.

Run with PYSTACHY_LLVM set for JIT/AOT checks. Set
PYSTACHY_SKEW_TEST_COMPILER to a native compiler command to reuse the same checks
after bootstrapping; otherwise they use the CPython-hosted compiler.
"""
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("skewprofile", ROOT / "tools/skewprofile.py")
profile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(profile)


class CensusTests(unittest.TestCase):
    @staticmethod
    def observe(census, value=None, *, missing=False, module="__main__", function="consume", event="call"):
        frame = SimpleNamespace(f_globals={"__name__": module},
                                f_code=SimpleNamespace(co_qualname=function),
                                f_locals={} if missing else {"obj": value})
        census.observe(frame, event, None)

    def test_unknown_types_and_missing_parameters_stay_in_denominator(self):
        census = profile.Census("consume", "obj")
        for _ in range(89):
            self.observe(census, 1)
        unknown = type("not-an-identifier", (), {"__module__": "__main__"})()
        for _ in range(10):
            self.observe(census, unknown)
        self.observe(census, missing=True)
        self.assertEqual(census.total, 100)
        self.assertEqual(census.counts["<other>"], 11)
        self.assertEqual(census.rows(), [])

    def test_sample_and_skew_thresholds_include_exact_boundary(self):
        for hits, total, selected in [(99, 99, False), (89, 100, False), (90, 100, True), (180, 200, True)]:
            with self.subTest(hits=hits, total=total):
                census = profile.Census("consume", "obj")
                for _ in range(hits):
                    self.observe(census, 1)
                for _ in range(total - hits):
                    self.observe(census, None)
                expected = [f"consume\tobj\tbuiltins.int\t{hits}\t{total}"] if selected else []
                self.assertEqual(census.rows(), expected)

    def test_bool_and_int_have_separate_exact_identities(self):
        census = profile.Census("consume", "obj")
        self.observe(census, True)
        self.observe(census, 1)
        self.assertEqual(dict(census.counts), {"builtins.bool": 1, "builtins.int": 1})

    def test_identity_does_not_invoke_metaclass_attribute_or_hash_hooks(self):
        calls = []

        class Hostile(type):
            def __getattribute__(cls, name):
                calls.append(name)
                raise AssertionError("user metaclass attribute hook called")

            def __hash__(cls):
                calls.append("hash")
                raise AssertionError("user metaclass hash hook called")

        receiver = Hostile("Hot", (), {"__module__": "__main__", "__qualname__": "Hot"})()
        census = profile.Census("consume", "obj")
        for _ in range(100):
            self.observe(census, receiver)
        self.assertEqual(census.rows(), [])
        self.assertEqual(census.counts["<other>"], 100)
        self.assertEqual(calls, [])

    def test_unrelated_events_and_main_module_prefix_are_excluded(self):
        census = profile.Census("pkg.consume", "obj")
        self.observe(census, 1)
        self.observe(census, 1, module="pkg", event="return")
        self.observe(census, 1, module="pkg", function="other")
        self.observe(census, 1, module="pkg")
        self.assertEqual(census.total, 1)
        self.assertEqual(profile.identity(type("Hot", (), {"__module__": "__main__"})), "Hot")
        self.assertEqual(profile.identity(type("Hot", (), {"__module__": "pkg"})), "pkg.Hot")

    def test_class_census_is_bounded_without_losing_total_calls(self):
        census = profile.Census("consume", "obj")
        for i in range(profile.MAX_CLASSES + 20):
            value = type(f"Class{i}", (), {"__module__": "__main__"})()
            self.observe(census, value)
        self.assertLessEqual(len(census.counts), profile.MAX_CLASSES + 1)
        self.assertEqual(census.total, profile.MAX_CLASSES + 20)
        self.assertEqual(census.counts["<other>"], 20)
        self.assertEqual(sum(census.counts.values()), census.total)


CLASSES = """
class Base:
    def value(self) -> int:
        return 1

class Hot(Base):
    def value(self) -> int:
        return 10

class Cold(Base):
    def value(self) -> int:
        return 20

class More(Hot):
    def value(self) -> int:
        return 30
"""

SIMPLE = CLASSES + """
def consume(obj: Base) -> int:
    return obj.value()

receiver: Base = Hot()
print(consume(receiver))
"""

SEMANTICS = CLASSES + """
from typing import Callable

evaluations = 0
bodies = 0

def argument(value: int) -> int:
    global evaluations
    evaluations += 1
    return value

def default() -> int:
    print("default")
    return 7

def consume(obj: Base, extra: int = default()) -> int:
    global bodies
    bodies += 1
    return obj.value() + extra

def action(obj: Base, fail: bool) -> None:
    print("action", obj.value())
    try:
        if fail:
            raise ValueError("expected")
    finally:
        print("finally", obj.value())

def never(obj: Base) -> int:
    raise ValueError(str(obj.value()))

items: list[Base] = [Hot(), Cold(), More(), Base()]
for receiver in items:
    print(consume(receiver, argument(3)))
    print(consume(extra=argument(4), obj=receiver))
    print(consume(receiver))
    action(receiver, False)
    try:
        action(receiver, True)
    except ValueError as error:
        print("caught", error)
    try:
        print(never(receiver))
    except ValueError as error:
        print("never", error)

callback: Callable[[Base, int], int] = consume
print("callback", callback(Hot(), argument(5)))
try:
    print(consume(None, argument(6)))
except AttributeError:
    print("none")
print("counts", evaluations, bodies)
"""


class CompilerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-skew-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.program = self.directory / "case.py"
        self.hints = self.directory / "case.profile"
        self.compiler = shlex.split(os.environ["PYSTACHY_SKEW_TEST_COMPILER"]) if os.environ.get(
            "PYSTACHY_SKEW_TEST_COMPILER") else [sys.executable, "-m", "pystachy"]
        self.env = dict(os.environ, PYSTACHY_HOME=str(ROOT))
        self.env.pop("PYSTACHY_SKEW_PROFILE", None)
        self.env.pop("PYSTACHY_IRFX", None)

    def write(self, source):
        self.program.write_text(textwrap.dedent(source), encoding="utf-8")

    def hint(self, rows="consume\tobj\tHot\t900\t1000", header=profile.HEADER):
        self.hints.write_text(header + "\n" + rows + "\n", encoding="utf-8")

    def invoke(self, *arguments, hints=False, successful=True):
        env = dict(self.env)
        if hints:
            env["PYSTACHY_SKEW_PROFILE"] = str(self.hints)
        result = subprocess.run([*self.compiler, *map(str, arguments)], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        if successful:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    @staticmethod
    def definitions(ir):
        return set(re.findall(r"^define [^@\n]*(@[^ (]+)\(", ir, re.MULTILINE))

    def ir(self, hints=False, successful=True):
        return self.invoke("ir", self.program, hints=hints, successful=successful)

    def test_skew_adds_clone_and_exact_tag_guard_with_baseline_fallback(self):
        self.write(SIMPLE)
        self.hint()
        baseline = self.ir().stdout
        specialized = self.ir(hints=True).stdout
        added = self.definitions(specialized) - self.definitions(baseline)
        self.assertEqual(len(added), 1, str(added))
        clone = next(iter(added))
        self.assertIn("consume", clone)
        self.assertRegex(specialized, rf"call i64 {re.escape(clone)}\(")
        self.assertRegex(specialized, r"icmp eq i64 %[^,]+, [0-9]+")
        self.assertRegex(specialized, r"icmp eq ptr %[^,]+, null")
        self.assertIn("call i64 @f.consume(", specialized)

    def test_bad_or_unqualified_profiles_leave_ir_unchanged(self):
        self.write(SIMPLE)
        baseline = self.ir().stdout
        cases = [
            (profile.HEADER, "consume\tobj\tHot\t99\t99"),
            (profile.HEADER, "consume\tobj\tHot\t89\t100"),
            (profile.HEADER, "consume\tobj\tHot\t101\t100"),
            (profile.HEADER, "consume\tobj\tHot\t-1\t100"),
            (profile.HEADER, "consume\tobj\tHot\t90.0\t100"),
            (profile.HEADER, "consume\tobj\tHot\t900\t1000\textra"),
            (profile.HEADER, "consume\tobj\tHot\t900\t1000\nconsume\tobj\tCold\t900\t1000"),
            (profile.HEADER, "consume\tmissing\tHot\t900\t1000"),
            (profile.HEADER, "consume\tobj\tMissing\t900\t1000"),
            (profile.HEADER, "__main__.consume\tobj\tHot\t900\t1000"),
            ("pystachy-skew-v0", "consume\tobj\tHot\t900\t1000"),
            (profile.HEADER, "x" * 65536),
        ]
        for header, rows in cases:
            with self.subTest(rows=rows[:100], header=header):
                self.hint(rows, header)
                self.assertEqual(self.ir(hints=True).stdout, baseline)
        self.hints.unlink()
        self.assertEqual(self.ir(hints=True).stdout, baseline)

    def test_profiles_cannot_hide_original_body_or_argument_type_errors(self):
        programs = [
            SIMPLE.replace("return obj.value()", 'return "wrong"'),
            SIMPLE.replace("return obj.value()", "return obj.hot_only()")
            .replace("class Hot(Base):", "class Hot(Base):\n    def hot_only(self) -> int:\n        return 123\n"),
            SIMPLE.replace("consume(receiver)", 'consume("wrong")'),
            SIMPLE.replace("def consume(obj: Base) -> int:", "def consume(obj: Base):"),
        ]
        self.hint()
        for source in programs:
            with self.subTest(source=source[-150:]):
                self.write(source)
                baseline = self.ir(successful=False)
                specialized = self.ir(hints=True, successful=False)
                self.assertNotEqual(baseline.returncode, 0)
                self.assertEqual(specialized.returncode, baseline.returncode)
                self.assertEqual(specialized.stderr, baseline.stderr)

    def test_reassigned_captured_unannotated_and_callable_calls_use_baseline(self):
        programs = [
            SIMPLE.replace("return obj.value()", "obj = Cold()\n    return obj.value()"),
            SIMPLE.replace("return obj.value()", "def inner() -> int:\n        return obj.value()\n    return inner()"),
            SIMPLE.replace("return obj.value()", "alias = obj\n    alias = Cold()\n    return alias.value()"),
            SIMPLE.replace("return obj.value()", "alias = obj.value()\n    return alias"),
            SIMPLE.replace("obj: Base", "obj"),
            "from typing import Callable\n" + SIMPLE.replace(
                "print(consume(receiver))", "callbacks: list[Callable[[Base], int]] = [consume]\nprint(callbacks[0](receiver))"),
            SIMPLE.replace("obj: Base)", "obj: Base, *args: int)"),
            SIMPLE.replace("obj: Base)", "obj: Base, **kwargs: int)"),
        ]
        self.hint()
        for source in programs:
            with self.subTest(source=source[-200:]):
                self.write(source)
                self.assertEqual(self.ir(hints=True).stdout, self.ir().stdout)

    def test_imported_function_and_class_require_fully_qualified_identity(self):
        (self.directory / "receivers.py").write_text(SIMPLE.replace("receiver: Base = Hot()\nprint(consume(receiver))", ""))
        self.write("from receivers import Base, Hot, consume\nreceiver: Base = Hot()\nprint(consume(receiver))\n")
        baseline = self.ir().stdout
        self.hint("receivers.consume\tobj\treceivers.Hot\t90\t100")
        self.assertEqual(len(self.definitions(self.ir(hints=True).stdout) - self.definitions(baseline)), 1)
        self.hint("consume\tobj\tHot\t90\t100")
        self.assertEqual(self.ir(hints=True).stdout, baseline)

    def test_profile_cloning_stops_at_sixteen_functions(self):
        names = [f"consume{i}" for i in range(18)]
        source = CLASSES + "\n".join(f"def {name}(obj: Base) -> int:\n    return obj.value()\n" for name in names)
        source += "receiver: Base = Hot()\nprint(" + " + ".join(f"{name}(receiver)" for name in names) + ")\n"
        self.write(source)
        self.hint("\n".join(f"{name}\tobj\tHot\t90\t100" for name in names))
        baseline = self.ir().stdout
        specialized = self.ir(hints=True).stdout
        self.assertEqual(len(self.definitions(specialized) - self.definitions(baseline)), 16)

    def test_nested_specialization_reserves_budget_before_validating_callees(self):
        source = """
from __future__ import annotations
class Base:
    def next(self) -> Base:
        return self
    def value(self) -> int:
        return 1
class Hot(Base):
    def next(self) -> Base:
        return self
    def value(self) -> int:
        return 2
"""
        names = [f"consume{i}" for i in range(20)]
        for i, name in enumerate(names):
            result = f"{names[i + 1]}(obj.next())" if i + 1 < len(names) else "obj.value()"
            source += f"\ndef {name}(obj: Base) -> int:\n    return {result}\n"
        source += "\nprint(consume0(Hot()))\n"
        self.write(source)
        self.hint("\n".join(f"{name}\tobj\tHot\t90\t100" for name in names))
        baseline = self.ir().stdout
        specialized = self.ir(hints=True).stdout
        self.assertEqual(len(self.definitions(specialized) - self.definitions(baseline)), 16)

    def test_covariant_method_results_cannot_retype_downstream_template_aliases(self):
        source = """
from __future__ import annotations
class Base:
    def make(self) -> Base:
        return self
class Hot(Base):
    def make(self) -> Hot:
        return self
class Cold(Base):
    def make(self) -> Base:
        return self

def helper(value) -> int:
    alias = value
    alias = Base()
    return 1

def consume(obj: Base) -> int:
    return helper(obj.make())

print(consume(Hot()))
"""
        variants = [
            (source, False),
            (source.replace("def make(self) -> Hot:", "def make(self) -> Base:").replace(
                "class Cold(Base):\n    def make(self) -> Base:", "class Cold(Base):\n    def make(self) -> Cold:"), False),
            (source.replace("def make(self) -> Hot:", "def make(self) -> Base:"), True),
        ]
        self.hint()
        for program, eligible in variants:
            with self.subTest(eligible=eligible, program=program[:300]):
                self.write(program)
                baseline = self.ir().stdout
                specialized = self.ir(hints=True).stdout
                if eligible:
                    self.assertEqual(len(self.definitions(specialized) - self.definitions(baseline)), 1)
                else:
                    self.assertEqual(specialized, baseline)

    def test_jit_aot_match_cpython_for_hot_miss_subclass_none_and_exceptions(self):
        from pystachy import llvm_dir
        directory = llvm_dir()
        if not directory or not (Path(directory) / "lli").exists():
            self.skipTest("set PYSTACHY_LLVM to run native semantics checks")
        self.write(SEMANTICS)
        self.hint("\n".join(f"{name}\tobj\tHot\t900\t1000" for name in ["consume", "action", "never"]))
        expected = subprocess.run([sys.executable, str(self.program)], capture_output=True, text=True,
                                  check=True, timeout=30).stdout
        self.assertIn("counts 10 14\n", expected)
        baseline_ir = self.ir().stdout
        specialized_ir = self.ir(hints=True).stdout
        self.assertEqual(len(self.definitions(specialized_ir) - self.definitions(baseline_ir)), 3)
        for hints in [False, True]:
            with self.subTest(mode="jit", hints=hints):
                self.assertEqual(self.invoke("run", self.program, hints=hints).stdout, expected)
            with self.subTest(mode="aot", hints=hints):
                executable = self.directory / ("specialized" if hints else "baseline")
                self.invoke("build", self.program, "-o", executable, hints=hints)
                result = subprocess.run([str(executable)], cwd=ROOT, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_stdlib_html_callback_workload_with_held_out_types(self):
        workload = ROOT / "bench/skew_html.py"
        recording = subprocess.run(
            [sys.executable, str(ROOT / "tools/skewprofile.py"), "--function", "parse_documents",
             "--parameter", "parser", "--output", str(self.hints), str(workload), "train"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=30,
        )
        self.assertIn('"calls": 200', recording.stdout)
        self.assertIn("parse_documents\tparser\tLinkParser\t199\t200", self.hints.read_text())
        baseline_ir = self.invoke("ir", workload).stdout
        profile_ir = self.invoke("ir", workload, hints=True).stdout
        self.assertIn("@f.parse_documents.1", self.definitions(profile_ir) - self.definitions(baseline_ir))
        expected = subprocess.run([sys.executable, str(workload), "check"], cwd=ROOT,
                                  capture_output=True, text=True, check=True, timeout=30).stdout
        self.assertEqual(expected, "check 171600 33 297 2088\n")
        for hints in [False, True]:
            self.assertEqual(self.invoke("run", workload, "check", hints=hints).stdout, expected)
            executable = self.directory / ("html-profile" if hints else "html-baseline")
            self.invoke("build", workload, "-o", executable, hints=hints)
            for stress in ["", "1"]:
                env = dict(self.env, PYSTACHY_GC_STRESS=stress)
                result = subprocess.run([str(executable), "check"], cwd=ROOT, env=env,
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)


if __name__ == "__main__":
    unittest.main()
