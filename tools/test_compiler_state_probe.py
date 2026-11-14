"""Mutation-sensitive audit and fresh-pass controls; no LLVM tools required."""
import inspect
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from compiler_state_probe import ROOT, Snapshot
from src.pystachy_compiler import driver
from src.pystachy_compiler.diagnostics import NeedHierarchy, Rejoin
from src.pystachy_compiler.ir import FnInfo
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.syntax import Node


class StateProbeTests(unittest.TestCase):
    def test_same_size_and_nested_mutations(self):
        f = FnInfo("f", "@f.f", Node("def", "f", 1), "")
        roots = {"gtypes": {"xs": "list[?]"}, "funcs": {"f": f}}
        before = Snapshot(roots)
        roots["gtypes"]["xs"] = "list[int]"
        f.ret = "str"
        self.assertEqual(before.changed(roots), ["funcs", "gtypes"])

    def test_alias_replacement_and_cycles(self):
        values = [1]
        values.append(values)
        roots = {"left": values, "right": values}
        before = Snapshot(roots)
        self.assertEqual(before.changed(roots), [])
        replacement = [1]
        replacement.append(replacement)
        roots["right"] = replacement
        self.assertEqual(before.changed(roots), ["right"])

    def test_same_size_list_mutation(self):
        roots = {"FILES": ["first.py", "second.py"]}
        before = Snapshot(roots)
        roots["FILES"][1] = "wrong.py"
        self.assertEqual(before.changed(roots), ["FILES"])

    def test_unknown_snapshot_type_fails_closed(self):
        with self.assertRaises(TypeError):
            Snapshot({"unknown": object()})

    def restart_contract(self, compile_fn):
        # Exercise the real driver's catch/rewind path. Synthetic loader/program
        # effects make each expected rewind necessary, including link-prefix retention.
        names = ("LAMBDAS", "RENAMED", "LIBS", "LINKDL")
        saved = {name: getattr(driver, name).copy() for name in names}
        generations = []

        class FakeLoader:
            def __init__(self, dirs):
                pass

            def program(self, path, source):
                return source

        test = self

        class FakeGen:
            def __init__(self):
                self.newhints = {}
                self.newx = {}
                self.gtypes = {}
                self.idevent = ""
                self.idhint = {}
                generations.append(self)

            def program(self, source):
                test.assertEqual(driver.LAMBDAS, [11])
                test.assertEqual(driver.RENAMED, {})
                test.assertEqual(driver.LIBS, ["prefix-lib"])
                test.assertEqual(driver.LINKDL, ["prefix-dl"])
                test.assertEqual(self.gtypes, {})
                if len(generations) == 1:
                    driver.LAMBDAS[0] += 5
                    driver.RENAMED["tmp"] = "aborted"
                    driver.LIBS.append("aborted-lib")
                    driver.LINKDL.append("aborted-dl")
                    self.gtypes["xs"] = "list[int]"
                    self.newhints["join"] = "union[int,str]"
                    self.newx["A.__eq__"] = True
                    raise Rejoin()
                test.assertEqual(self.hints, {"join": "union[int,str]"})
                test.assertEqual(self.xnot, {"A.__eq__": True})
                return "clean pass"

        try:
            driver.LAMBDAS[:] = [11]
            driver.RENAMED.clear()
            driver.LIBS[:] = ["prefix-lib"]
            driver.LINKDL[:] = ["prefix-dl"]
            with patch.dict(compile_fn.__globals__, Gen=FakeGen, Loader=FakeLoader):
                self.assertEqual(compile_fn("probe.py", "", [], ""), "clean pass")
            self.assertEqual(len(generations), 2)
            self.assertIsNot(generations[0], generations[1])
        finally:
            for name, value in saved.items():
                target = getattr(driver, name)
                if isinstance(target, list):
                    target[:] = value
                else:
                    target.clear()
                    target.update(value)

    def test_hierarchy_retries_keep_only_names_and_do_not_spend_join_budget(self):
        generations = []
        test = self

        class FakeLoader:
            def __init__(self, dirs):
                pass

            def program(self, path, source):
                return source

        class FakeGen:
            def __init__(self):
                self.gtypes = {}
                generations.append(self)

            def program(self, source):
                test.assertEqual(self.gtypes, {})
                test.assertFalse(self.final)
                test.assertEqual(self.hints, {})
                test.assertEqual(self.xnot, {})
                count = len(self.hierarchies)
                if count < 12:
                    self.gtypes["tentative"] = "list[int]"
                    self.hints["old-layout"] = "helper$Base#1"
                    self.xnot["protocol:old-layout"] = True
                    self.hierarchies[f"helper$Child{count}"] = True
                    raise NeedHierarchy()
                return str(count)

        with patch.dict(driver.compile_program.__globals__, Gen=FakeGen, Loader=FakeLoader):
            self.assertEqual(driver.compile_program("hierarchy.py", "", [], ""), "12")
            self.assertEqual(driver.compile_program("other.py", "", [], ""), "12")
        self.assertEqual(len(generations), 26)
        self.assertEqual(len({id(g) for g in generations}), 26)
        self.assertIsNot(generations[0].hierarchies, generations[13].hierarchies)

    def test_fixed_layout_restores_template_registry_after_retry_and_error(self):
        generator = Gen()
        templates = {"Base": True, "Unrelated": True}
        generator.tmpl = templates
        node = Node("class", "Base", 1)
        for error in (NeedHierarchy(), SystemExit(1)):
            def interrupted(gen, st, error=error):
                self.assertEqual(gen.tmpl, {"Unrelated": True})
                raise error

            with self.subTest(error=type(error).__name__):
                with patch.object(Gen, "fixed_layout_body", interrupted):
                    with self.assertRaises(type(error)):
                        generator.fixed_layout(node)
                self.assertIs(generator.tmpl, templates)
                self.assertEqual(templates, {"Base": True, "Unrelated": True})

    def test_local_fixed_hierarchies_batch_declaration_retries(self):
        source = "class Base:\n    def __init__(self, values):\n        self.value: int = len(values)\n"
        source += "".join(f"class Child{i}(Base):\n    pass\n" for i in range(25))
        source += "print(Child0([1, 2]).value)\n"
        original = Gen.program
        attempts = []

        def counted(gen, mods):
            attempts.append(gen)
            return original(gen, mods)

        with patch.object(Gen, "program", counted):
            ir = driver.compile_program("hierarchy-batch.py", source, [], "")
        self.assertIn("@main", ir)
        self.assertEqual(len(attempts), 2)

    def test_restart_rewinds_known_globals_and_uses_fresh_gen(self):
        self.restart_contract(driver.compile_program)

    def ctypes_link_restart_contract(self, compile_fn, prefix):
        # Exercise the real CDLL lowering and ffi.load_library builtin, including
        # an unused library: no @extern declaration can mask its link requirement.
        source = "import ctypes\nlibrary = ctypes.CDLL(None)\nprint(1)\n"
        names = ("LAMBDAS", "RENAMED", "LIBS", "LINKDL")
        saved = {name: getattr(driver, name).copy() for name in names}
        builtin, program = Gen.builtin, Gen.program
        try:
            driver.LINKDL[:] = prefix
            expected = driver.compile_program("ctypes_state.py", source, [str(ROOT / "lib")], "")
            wanted = prefix or ["dl"]
            self.assertEqual(driver.LINKDL, wanted)
            driver.LINKDL[:] = prefix
            entries, generated = [], []

            def entering(gen, mods):
                entries.append(driver.LINKDL.copy())
                self.assertEqual(driver.LINKDL, prefix)
                return program(gen, mods)

            def retry_after_builtin(gen, name, args, want, resultsoft=False):
                result = builtin(gen, name, args, want, resultsoft)
                if name == "ffi.load_library":
                    generated.append(driver.LINKDL.copy())
                    self.assertEqual(driver.LINKDL, wanted)
                    if len(generated) == 1:
                        raise Rejoin()
                return result

            with patch.object(Gen, "program", entering), patch.object(Gen, "builtin", retry_after_builtin):
                actual = compile_fn("ctypes_state.py", source, [str(ROOT / "lib")], "")
            self.assertEqual(actual, expected)
            self.assertEqual(entries, [prefix, prefix])
            self.assertEqual(generated, [wanted, wanted])
            self.assertEqual(driver.LINKDL, wanted)
        finally:
            for name, value in saved.items():
                target = getattr(driver, name)
                if isinstance(target, list):
                    target[:] = value
                else:
                    target.clear()
                    target.update(value)

    def test_ctypes_library_link_requirement_rewinds_on_retry(self):
        for prefix in ([], ["entry-dl"]):
            with self.subTest(prefix=prefix):
                self.ctypes_link_restart_contract(driver.compile_program, prefix)

    def test_missing_ctypes_link_rewind_is_detected(self):
        source = inspect.getsource(driver.compile_program)
        namespace = dict(vars(driver))
        exec(compile(source.replace("LINKDL.pop()", "break"), "<missing-ctypes-link-rewind>", "exec"), namespace)
        with self.assertRaises(AssertionError):
            self.ctypes_link_restart_contract(namespace["compile_program"], [])

    def test_identity_restart_starts_over_tracking_everywhere(self):
        # A crossing into code that tracks numeric identity (Gen.identity_event) discards the
        # aborted pass's joins and comparison retries: the next pass is the first of a program
        # whose every module tracks identity (idfull).
        names = ("LAMBDAS", "RENAMED", "LIBS", "LINKDL")
        saved = {name: getattr(driver, name).copy() for name in names}
        generations = []
        test = self

        class FakeLoader:
            def __init__(self, dirs):
                pass

            def program(self, path, source):
                return source

        class FakeGen:
            def __init__(self):
                self.newhints = {}
                self.newx = {}
                self.idevent = ""
                self.idhint = {}
                generations.append(self)

            def program(self, source):
                if len(generations) == 1:
                    test.assertFalse(self.idfull)
                    self.newhints["join"] = "union[int,str]"
                    self.newx["A.__eq__"] = True
                    self.idevent = "number as an Any value"
                    raise Rejoin()
                test.assertTrue(self.idfull)
                test.assertEqual(self.hints, {})
                test.assertEqual(self.xnot, {})
                test.assertFalse(self.final)
                return "tracking pass"

        try:
            with patch.dict(driver.compile_program.__globals__, Gen=FakeGen, Loader=FakeLoader):
                self.assertEqual(driver.compile_program("probe.py", "", [], ""), "tracking pass")
            self.assertEqual(len(generations), 2)
        finally:
            for name, value in saved.items():
                target = getattr(driver, name)
                if isinstance(target, list):
                    target[:] = value
                else:
                    target.clear()
                    target.update(value)

    def test_identity_hint_retry_precedes_full_tracking(self):
        generations = []
        test = self

        class FakeLoader:
            def __init__(self, dirs):
                pass

            def program(self, path, source):
                return source

        class FakeGen:
            def __init__(self):
                self.newhints = {}
                self.newx = {}
                self.idevent = ""
                self.idhint = {}
                generations.append(self)

            def program(self, source):
                test.assertEqual(self.hints, {})
                test.assertEqual(self.xnot, {})
                test.assertFalse(self.final)
                if len(generations) < 3:
                    test.assertFalse(self.idfull)
                    test.assertEqual(self.idtry, len(generations) == 1)
                    self.idhint = {"hinted": True} if self.idtry else {}
                    self.newhints["dirty"] = "int"
                    self.newx["dirty"] = True
                    self.idevent = "unsafe crossing"
                    raise Rejoin()
                test.assertFalse(self.idtry)
                test.assertTrue(self.idfull)
                return "full tracking"

        with patch.dict(driver.compile_program.__globals__, Gen=FakeGen, Loader=FakeLoader):
            self.assertEqual(driver.compile_program("probe.py", "", [], ""), "full tracking")
        self.assertEqual(len(generations), 3)

    def test_each_missing_rewind_is_detected(self):
        source = inspect.getsource(driver.compile_program)
        for reset in ("LAMBDAS[0] = lambdas", "RENAMED.clear()",
                      "LIBS.pop()", "LINKDL.pop()"):
            with self.subTest(reset=reset):
                # break exits a truncation loop without rewinding; removing pop
                # alone would make the negative control loop forever.
                broken = source.replace(reset, "break" if reset.endswith(".pop()") else "pass")
                namespace = dict(vars(driver))
                exec(compile(broken, "<missing-rewind>", "exec"), namespace)
                with self.assertRaises(AssertionError):
                    self.restart_contract(namespace["compile_program"])

    def run_probe(self, case, baseline=False):
        command = [sys.executable, str(ROOT / "tools/compiler_state_probe.py"), case]
        if baseline:
            command.append("--baseline")
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_real_dry_calls_preserve_emission_and_ir(self):
        for case in ("tests/programs/inference/dynany_eq_template.py",
                     "tools/fixtures/compiler_state_dry_template.py"):
            with self.subTest(case=case):
                observed = self.run_probe(case)
                baseline = self.run_probe(case, baseline=True)
                self.assertEqual(observed["ir_sha256"], baseline["ir_sha256"])
                self.assertGreater(len(observed["dry_calls"]), 0)
                self.assertTrue(any(e["outcome"] == "returned" for e in observed["dry_calls"]))

    def test_corrupted_dry_restore_is_detected(self):
        script = '''
import sys
sys.path.insert(0, "tools")
from compiler_state_probe import Gen, probe
original = Gen.dry
def broken(g, node, want=""):
    result = original(g, node, want)
    g.line += 1
    return result
Gen.dry = broken
probe("tools/fixtures/compiler_state_dry_template.py")
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, text=True,
                                capture_output=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("successful dry changed saved emission: ['line']", result.stderr)

    def test_global_inference_reproducer_keeps_valid_method(self):
        case = "tests/programs/inference/dynany_eq_restart_global.py"
        observed = self.run_probe(case)
        self.assertEqual(observed["ir_sha256"], self.run_probe(case, True)["ir_sha256"])
        self.assertGreater(len(observed["passes"]), 1)
        last = observed["passes"][-1]
        self.assertEqual(last["outcome"], "returned")
        self.assertEqual(last["declined_in"], ["A.__eq__"])
        self.assertEqual(observed["passes"][0]["global_types"]["xs"], "list[int]")
        self.assertEqual(last["global_types"]["xs"], "list[str]")
        result = subprocess.run([sys.executable, str(ROOT / case)], text=True,
                                capture_output=True, timeout=10, check=True)
        self.assertEqual(result.stdout, "True\n")


if __name__ == "__main__":
    unittest.main()
