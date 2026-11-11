"""Representation observations distinguish tuple storage contracts from views."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import inspect_compiler


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler.ir import Data, Ins, Val  # noqa: E402


class LayoutMetadataTests(unittest.TestCase):
    def observer(self):
        return inspect_compiler.Observer({}, Path("unused"), "")

    @staticmethod
    def function(operations, parameters=()):
        return SimpleNamespace(f=SimpleNamespace(ptypes=list(parameters)), slots=[],
                               blocks=[SimpleNamespace(code=operations)])

    @staticmethod
    def definition(op, representation, number):
        instruction = Ins(op, representation, "")
        instruction.r = [number]
        return instruction

    def test_mixed_nested_definition_and_parameter_are_not_all_promoting(self):
        observer = self.observer()
        allocation = self.definition("alloc.fixed", "tuple[int,tuple[int+,int]]", 1)
        unpack = self.definition("slot.unpack", "tuple[int,int+]", 2)
        fn = self.function([allocation, unpack], ["tuple[int,int]"])
        metadata = observer.representation_metadata(fn)
        self.assertEqual(metadata["version"], 1)
        sources = {source["value"]: source for source in metadata["sources"]}
        self.assertEqual(sources["%a0"]["representation"], "tuple[int,int]")
        self.assertEqual(sources["%t1"]["representation"], "tuple[int,tuple[int+,int]]")
        self.assertEqual(sources["%t1"]["origin"], "allocation")
        self.assertEqual(sources["%t2"]["representation"], "tuple[int,int+]")

    def test_only_live_identical_producer_keeps_observed_container_origin(self):
        observer = self.observer()
        original = self.definition("slot.unpack", "tuple[int,int]", 3)
        fn = self.function([original])
        observer.record_representation(SimpleNamespace(fn=fn), Val("%t3", original.t),
                                       "tuple[int+,int+]", "held_value")
        self.assertEqual(observer.representation_metadata(fn)["sources"][0]["origin"], "held_value")
        # A dry/retry can reuse %t3 for a completely different instruction object.
        replacement = self.definition("slot.unpack", "tuple[int,int]", 3)
        fn.blocks[0].code = [replacement]
        self.assertEqual(observer.representation_metadata(fn)["sources"][0]["origin"], "definition")
        # Rewriting the original producer also invalidates its earlier observation.
        fn.blocks[0].code = [original]
        original.a = [Val("%different", "%slot")]
        self.assertEqual(observer.representation_metadata(fn)["sources"][0]["origin"], "definition")

    def test_explicit_clone_transfers_only_valid_object_provenance(self):
        from src.pystachy_compiler.optimizations import clone_instruction
        observer = self.observer()
        original = self.definition("slot.unpack", "tuple[int,int]", 3)
        original.a = [Val("%t2", "%slot")]
        original.b = ["success"]
        fn = self.function([original])
        observer.record_representation(SimpleNamespace(fn=fn), Val("%t3", original.t),
                                       "tuple[int+,int+]", "held_value")
        wrapped = observer.clone_instruction_wrapper(clone_instruction)
        clone = wrapped(original, {2: 20, 3: 30}, {"success": "cloned"})
        fn.blocks[0].code = [clone]
        source = observer.representation_metadata(fn)["sources"][0]
        self.assertEqual(source["value"], "%t30")
        self.assertEqual(source["representation"], "tuple[int+,int+]")
        self.assertEqual(source["origin"], "held_value")
        # The observer validates the clone object and updates its signature.
        clone.a = [Val("%wrong", "%slot")]
        self.assertEqual(observer.representation_metadata(fn)["sources"][0]["origin"], "definition")
        fn.blocks[0].code = [self.definition("slot.unpack", "tuple[int,int]", 30)]
        self.assertEqual(observer.representation_metadata(fn)["sources"][0]["origin"], "definition")
        original.a = [Val("%changed", "%slot")]
        fn.blocks[0].code = [wrapped(original, {3: 40}, {})]
        self.assertEqual(observer.representation_metadata(fn)["sources"][0]["origin"], "definition")

    def test_malformed_clone_renaming_cannot_borrow_observation(self):
        from src.pystachy_compiler.optimizations import clone_instruction
        for mode in ("operand", "type", "descriptor", "target", "overlap"):
            with self.subTest(mode=mode):
                observer = self.observer()
                original = self.definition("slot.unpack", "tuple[int,int]", 3)
                original.a, original.b = [Val("%t2", "%slot")], ["success"]
                fn = self.function([original])
                observer.record_representation(SimpleNamespace(fn=fn), Val("%t3", original.t),
                                               "tuple[int+,int+]", "held_value")

                def bad_clone(source, numbers, labels, mode=mode):
                    clone = clone_instruction(source, numbers, labels)
                    if mode == "operand":
                        clone.a[0].v = "%t21"
                    elif mode == "type":
                        clone.t = "tuple[int,str]"
                    elif mode == "descriptor":
                        clone.x = "changed"
                    elif mode == "target":
                        clone.b = ["other"]
                    return clone

                numbers = {2: 30, 3: 30} if mode == "overlap" else {2: 20, 3: 30}
                clone = observer.clone_instruction_wrapper(bad_clone)(original, numbers, {"success": "cloned"})
                fn.blocks[0].code = [clone]
                self.assertEqual(observer.representation_metadata(fn)["sources"][0]["origin"], "definition")

    def test_clone_cannot_overwrite_existing_target_provenance(self):
        from src.pystachy_compiler.optimizations import clone_instruction
        observer = self.observer()
        source = self.definition("slot.unpack", "tuple[int,int]", 3)
        source.a = [Val("%t2", "%slot")]
        target = clone_instruction(source, {2: 20, 3: 30}, {})
        fn = self.function([source, target])
        observer.record_representation(SimpleNamespace(fn=fn), Val("%t3", source.t),
                                       "tuple[int+,int+]", "held_value")
        observer.record_representation(SimpleNamespace(fn=fn), Val("%t30", target.t),
                                       "tuple[int,int]", "held_read")
        observer.clone_instruction_wrapper(lambda *args: target)(source, {2: 20, 3: 30}, {})
        entry = next(item for item in observer.representation_metadata(fn)["sources"] if item["value"] == "%t30")
        self.assertEqual(entry["origin"], "held_read")
        self.assertEqual(entry["representation"], "tuple[int,int]")

    def test_exception_successors_preserve_runtime_result_contract(self):
        observer = self.observer()
        operation = self.definition("rt", "tuple[K,V]", 4)
        operation.s = "dict.popitem"
        fn = self.function([operation])
        observer.record_representation(SimpleNamespace(fn=fn), Val("%t4", "tuple[str,tuple[int,int]]"),
                                       "tuple[str,tuple[int+,int+]]", "held_pair")
        operation.b = ["normal", "unwind"]
        source = observer.representation_metadata(fn)["sources"][0]
        self.assertEqual(source["origin"], "held_pair")
        self.assertEqual(source["definition_type"], "tuple[K,V]")

    def test_global_tuple_data_is_exported_without_source_literal_registry(self):
        observer = self.observer()
        constant = Data("tuple", "@builtin.pair")
        constant.items = [Val("17", "int"), Val("@label", "str")]
        observer.gen = SimpleNamespace(consts=[constant])
        operation = Ins("ret", "", "")
        operation.a = [Val(constant.name, "tuple[int+,str]")]
        source = observer.representation_metadata(self.function([operation]))["sources"][0]
        self.assertEqual(source, {"value": "@builtin.pair", "representation": "tuple[int,str]", "origin": "constant",
                                  "items": [{"value": "17", "representation": "int"},
                                            {"value": "@label", "representation": "str"}]})

    def test_search_hold_only_annotates_new_result_phi(self):
        from src.pystachy_compiler import diagnostics
        previous = diagnostics.INTFILES
        self.addCleanup(setattr, diagnostics, "INTFILES", previous)
        diagnostics.INTFILES = [0]
        observer = self.observer()
        phi = self.definition("phi", "opt[tuple[int,int]]", 4)
        fn = self.function([phi])
        gen = SimpleNamespace(fn=fn, n=4)
        value = Val("%t4", phi.t)
        unchanged = observer.search_hold_wrapper(lambda *args: value)
        self.assertIs(unchanged(gen, value, phi.t, "tuple[int,int]"), value)
        self.assertEqual(observer.representation_metadata(fn)["sources"][0]["origin"], "definition")

        def fresh(gen, value, element_type, container_type):
            result = self.definition("phi", element_type, 5)
            result.a = [Val("null", element_type), Val("%other", element_type)]
            fn.blocks[0].code.append(result)
            gen.n = 5
            return Val("%t5", element_type)

        observer.search_hold_wrapper(fresh)(gen, value, phi.t, "tuple[int,int]")
        source = next(s for s in observer.representation_metadata(fn)["sources"] if s["value"] == "%t5")
        self.assertEqual(source["origin"], "search_hold")
        self.assertEqual(source["representation"], "opt[tuple[int+,int+]]")
        self.assertEqual(source["definition_type"], "opt[tuple[int,int]]")

    def test_real_container_read_layout_and_plain_parameter(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "fixed.py").write_text(
                "def plain(t: tuple[int, int]) -> int:\n    return t[0]\n"
                "def first(xs: list[tuple[int, tuple[int, int]]]) -> tuple[int, tuple[int, int]]:\n"
                "    return xs[0]\n"
                "def pop(d: dict[str, tuple[int, int]]) -> tuple[str, tuple[int, int]]:\n"
                "    try:\n        return d.popitem()\n"
                "    except KeyError:\n        return ('empty', (0, 0))\n"
                "def contains(xs: list[tuple[int, int]], t: tuple[int, int] | None) -> bool:\n"
                "    return t in xs\n", encoding="utf-8")
            program = directory / "program.py"
            program.write_text(
                "# pystachy: python-int\nimport sys\nfrom fixed import first, plain, pop, contains\n"
                "def version() -> tuple[int, int, int, str, int]:\n    return sys.version_info\n"
                "print(first([(1, (2, 3))]))\nprint(plain((4, 5)))\n"
                "print(pop({'a': (6, 7)}), version() is sys.version_info)\n"
                "print(contains([(1, 2)], (1, 2)), contains([(1, 2)], None))\n", encoding="utf-8")
            output = directory / "inspection"
            environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            environment["PYSTACHY_HOME"] = str(ROOT)
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program), "--output", str(output)],
                cwd=ROOT, env=environment, text=True, capture_output=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stderr)
            snapshot = json.loads((output / "typed-after.json").read_text())
            functions = {fn["symbol"]: fn for fn in snapshot["functions"]}
            plain = functions["@f.fixed$plain"]["representation_metadata"]
            self.assertTrue(plain["int_containers"])
            parameter = next(source for source in plain["sources"] if source["value"] == "%a0")
            self.assertEqual(parameter["representation"], "tuple[int,int]")
            first = functions["@f.fixed$first"]["representation_metadata"]["sources"]
            held = [source for source in first if source["origin"] == "held_value"]
            self.assertEqual(len(held), 1)
            self.assertEqual(held[0]["definition_type"], "tuple[int,tuple[int,int]]")
            self.assertEqual(held[0]["representation"], "tuple[int+,tuple[int+,int+]]")
            pop = functions["@f.fixed$pop"]["representation_metadata"]["sources"]
            self.assertTrue(any(source["origin"] == "held_pair" and
                                source["representation"] == "tuple[str,tuple[int+,int+]]" for source in pop))
            for symbol in ("@main.init", "@f.version"):
                version = next(source for source in functions[symbol]["representation_metadata"]["sources"]
                               if source["value"] == "@sys.version_info")
                self.assertEqual(version["origin"], "constant")
                self.assertEqual(version["representation"], "tuple[int,int,int,str,int]")
                self.assertEqual([item["representation"] for item in version["items"]],
                                 ["int", "int", "int", "str", "int"])
            searches = [source for source in functions["@f.fixed$contains"]["representation_metadata"]["sources"]
                        if source["origin"] == "search_hold"]
            self.assertEqual(len(searches), 1)
            self.assertEqual(searches[0]["representation"], "opt[tuple[int+,int+]]")
            self.assertEqual(searches[0]["definition_type"], "opt[tuple[int,int]]")
            ordinary = subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "ir", str(program)],
                                      cwd=ROOT, env=environment, capture_output=True, timeout=40)
            self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
            self.assertEqual((output / "llvm.ll").read_bytes(), ordinary.stdout)


    def test_cloned_imported_tuple_read_keeps_held_layout(self):
        import check_lean_storage as storage
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "fixed.py").write_text(
                "def total(xs: list[tuple[int, int]], n: int) -> int:\n"
                "    result = 0\n    for i in range(n):\n        result += xs[i][0]\n    return result\n")
            program = directory / "program.py"
            program.write_text(
                "# pystachy: python-int\nfrom fixed import total\n"
                "large = 1 << 100\nprint(total([(1, large), (2, -large)], 2))\n"
                "print(total([(-9223372036854775808, large)], 1))\n")
            environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            environment["PYSTACHY_HOME"] = str(ROOT)
            snapshots = []
            for optimized in (True, False):
                output = directory / ("optimized" if optimized else "uncloned")
                env = dict(environment)
                if not optimized:
                    env["PYSTACHY_OPT"] = "-listguard"
                result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program),
                                         "--output", str(output), "--typed-after-only"],
                                        cwd=ROOT, env=env, text=True, capture_output=True, timeout=40)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                snapshot = json.loads((output / "typed-after.json").read_text())
                snapshots.append(snapshot)
                fn = next(fn for fn in snapshot["functions"] if fn["symbol"] == "@f.fixed$total")
                tuple_reads = {f"%t{op['results'][-1]}" for block in fn["blocks"] for op in block["operations"]
                               if op["op"] == "slot.unpack" and op["type"] == "tuple[int,int]"}
                sources = {entry["value"]: entry for entry in fn["representation_metadata"]["sources"]}
                self.assertEqual(len(tuple_reads), 2 if optimized else 1)
                for value in tuple_reads:
                    self.assertEqual(sources[value]["origin"], "held_value")
                    self.assertEqual(sources[value]["representation"], "tuple[int+,int+]")
                # Hosted observation must leave ordinary generated LLVM unchanged.
                ordinary = subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "ir", str(program)],
                                          cwd=ROOT, env=env, capture_output=True, timeout=40)
                self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
                self.assertEqual((output / "llvm.ll").read_bytes(), ordinary.stdout)
            if storage.DEFAULT_CHECKER.is_file():
                for snapshot in snapshots:
                    report, code = storage.check_all(snapshot)
                    self.assertEqual(code, 0, report)
                    self.assertEqual(report["totals"]["proved_obligations"], report["totals"]["obligations"])
                corrupted = copy.deepcopy(snapshots[0])
                fn = next(fn for fn in corrupted["functions"] if fn["symbol"] == "@f.fixed$total")
                marker_blocks = [block for block in fn["blocks"] if any(op["op"] == "scalar.cmp"
                                 and any(arg["value"] == "-9223372036854775808" for arg in op["operands"])
                                 for op in block["operations"]) and block["operations"][-1]["op"] == "cbr"]
                self.assertGreaterEqual(len(marker_blocks), 2)
                marker_blocks[-1]["operations"][-1]["targets"].reverse()
                report, code = storage.check_all(corrupted)
                self.assertEqual(code, 1, report)
            elif os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                self.fail("Lean checker required for clone-marker control")


if __name__ == "__main__":
    unittest.main()
