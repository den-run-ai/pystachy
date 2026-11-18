"""Actual class layouts, descriptor correspondence and boxed payload ABI controls."""
import copy
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import check_lean_boundary as bridge
import test_lean_boundary as fixtures
from src.pystachy_compiler.ir import Ins, Val
from src.pystachy_compiler.lowering import gen_lower_ins


ROOT = Path(__file__).resolve().parents[1]
CLANG = shutil.which(str(Path(os.environ["PYSTACHY_LLVM"]) / "clang") if os.environ.get("PYSTACHY_LLVM") else "clang")


class CheckerProtocolTests(unittest.TestCase):
    def result(self, reply, metadata):
        with mock.patch.object(bridge, "checker_result", return_value=reply):
            return bridge.run_checker("unused", "{}\n", metadata)

    def test_shared_protocol_accepts_other_checkers_without_layouts(self):
        reply = {"accepted": True, "nodes": 1, "payloads": 0}
        metadata = {"nodes": 1, "payloads": 0}
        self.assertTrue(self.result(reply, metadata))
        self.assertTrue(self.result({**reply, "layouts": 0}, metadata))
        for change in ({"nodes": True}, {"payloads": False}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "counts disagree"):
                self.result({**reply, **change}, metadata)
        with self.assertRaisesRegex(ValueError, "layout count"):
            self.result({**reply, "layouts": 1}, metadata)

    def test_class_obligations_require_exact_native_layout_count(self):
        metadata = {"nodes": 2, "payloads": 1, "layouts": 2}
        reply = {"accepted": True, "nodes": 2, "payloads": 1, "layouts": 2}
        self.assertTrue(self.result(reply, metadata))
        for change in ({"layouts": 0}, {"layouts": 1}, {"layouts": True}, {"extra": 0}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.result({**reply, **change}, metadata)
        del reply["layouts"]
        with self.assertRaisesRegex(ValueError, "checker error"):
            self.result(reply, metadata)


class LayoutMetadataTests(fixtures.SnapshotFixture):
    example = fixtures.CLASS_EXAMPLE
    function_filter = ""

    def test_validation_only_preserves_class_layout_obligations(self):
        candidate, metadata = bridge.normalize_snapshot(self.snapshot, "boundary_class", certify=False)
        self.assertEqual(candidate["certificate"], [])
        self.assertEqual(candidate["schema_version"], 3)
        self.assertEqual(len(candidate["layouts"]), 2)
        self.assertEqual(metadata["layouts"], 2)

    @unittest.skipUnless(fixtures.CHECKER.is_file(), "build tools/lean_boundary to check batch layouts")
    def test_batch_checker_preserves_layout_checks_between_candidates(self):
        candidate, metadata = bridge.normalize_snapshot(self.snapshot, "boundary_class")
        bad = copy.deepcopy(candidate)
        layout = next(entry for entry in bad["layouts"] if entry["tag"] == "@dt.Sub")
        layout["members"][0] = "str"
        for value, expected in ((candidate, True), (bad, False), (candidate, True)):
            self.assertEqual(bridge.run_checker(fixtures.CHECKER, bridge.encode(value), metadata), expected)

    def test_layout_inventory_matches_emitted_structs(self):
        llvm = (self.directory / "inspection/llvm.ll").read_text()
        entries = self.snapshot["dynamic_layouts"]
        self.assertEqual({entry["name"] for entry in entries}, {"Base", "Sub"})
        for entry in entries:
            declaration = re.search(r"^%C\." + re.escape(entry["name"]) + r" = type \{(.*)\}$", llvm, re.M)
            self.assertIsNotNone(declaration)
            self.assertEqual(declaration[1].split(", "), entry["llvm"])
            self.assertEqual(len(entry["members"]), len(entry["llvm"]))
            self.assertIn("dyn", entry["members"])  # numeric identity companion
            self.assertIn("bool", entry["members"])  # assignment flag

    def test_descriptor_words_match_emitted_constants(self):
        llvm = (self.directory / "inspection/llvm.ll").read_text()
        for entry in self.snapshot["dynamic_types"]:
            line = next(line for line in llvm.splitlines() if line.startswith(entry["symbol"] + " = "))
            words = re.findall(r"(?:i64|ptr) ([^,} ]+)", line)
            self.assertEqual(int(words[0]), entry["kind"])
            self.assertEqual(int(words[3]), entry["cls"])
            self.assertEqual(words[4], entry["base"] or "null")
            self.assertEqual(int(words[5]), entry["flags"])
            if entry["role"]:
                self.assertEqual(words[9], entry["role"])

    def test_descriptor_class_number_payload_and_ancestry_need_correspondence(self):
        for field, value in (("cls", 20), ("payload", "Other"), ("base", ""), ("role", "@dt.Base")):
            snapshot = copy.deepcopy(self.snapshot)
            descriptor = next(entry for entry in snapshot["dynamic_types"] if entry["symbol"] == "@dt.Sub")
            descriptor[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "descriptor and class layout disagree"):
                bridge.normalize_snapshot(snapshot, "boundary_class")

    def test_layout_inventory_is_required_complete_and_unique(self):
        for mode in ("missing", "omit", "duplicate"):
            snapshot = copy.deepcopy(self.snapshot)
            if mode == "missing":
                del snapshot["dynamic_layouts"]
            elif mode == "omit":
                snapshot["dynamic_layouts"].pop()
            else:
                snapshot["dynamic_layouts"].append(snapshot["dynamic_layouts"][0])
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                bridge.normalize_snapshot(snapshot, "boundary_class")

    @unittest.skipUnless(fixtures.CHECKER.is_file(), "build tools/lean_boundary to check layouts")
    def test_subclass_physical_layout_and_hidden_members_are_checked(self):
        candidate, metadata = bridge.normalize_snapshot(self.snapshot, "boundary_class")
        self.assertEqual(len(candidate["layouts"]), 2)
        self.assertEqual(metadata["layouts"], 2)
        self.assertTrue(fixtures.ProvedCheckerTests.check(self, candidate))
        for mode in ("member", "llvm", "missing", "order"):
            snapshot = copy.deepcopy(self.snapshot)
            layout = next(entry for entry in snapshot["dynamic_layouts"] if entry["name"] == "Sub")
            if mode == "member":
                # Same LLVM pointer width is not the same field representation.
                position = layout["members"].index("dyn")
                layout["members"][position] = "str"
            elif mode == "llvm":
                layout["llvm"][0] = "ptr"
            elif mode == "missing":
                layout["members"].pop()
                layout["llvm"].pop()
            else:
                layout["members"].reverse()
                layout["llvm"].reverse()
            candidate, _ = bridge.normalize_snapshot(snapshot, "boundary_class")
            with self.subTest(mode=mode):
                self.assertFalse(fixtures.ProvedCheckerTests.check(self, candidate))

    def test_forged_nonclass_kinds_cannot_hide_the_class_inventory(self):
        snapshot = copy.deepcopy(self.snapshot)
        for entry in snapshot["dynamic_types"]:
            entry["kind"] = 9
        with self.assertRaisesRegex(ValueError, "unknown class layout"):
            bridge.normalize_snapshot(snapshot, "boundary_class")

    @unittest.skipUnless(fixtures.CHECKER.is_file(), "build tools/lean_boundary to check layouts")
    def test_native_checker_rejects_deleted_layout_table_entries(self):
        for mode in ("empty", "omit", "downgrade", "duplicate"):
            candidate, _ = bridge.normalize_snapshot(self.snapshot, "boundary_class")
            if mode == "empty":
                candidate["layouts"] = []
            elif mode == "omit":
                candidate["layouts"].pop()
            elif mode == "duplicate":
                candidate["layouts"].append(candidate["layouts"][0])
            else:
                candidate["schema_version"] = 2
                del candidate["layouts"]
            result = subprocess.run([str(fixtures.CHECKER)], input=bridge.encode(candidate), text=True,
                                    capture_output=True, timeout=10)
            with self.subTest(mode=mode):
                self.assertEqual(result.returncode, 2)
                self.assertIn("layout", result.stdout)

    @unittest.skipUnless(fixtures.CHECKER.is_file(), "build tools/lean_boundary to check layouts")
    def test_native_checker_rejects_missing_layout_field(self):
        candidate, _ = bridge.normalize_snapshot(self.snapshot, "boundary_class")
        del candidate["layouts"]
        result = subprocess.run([str(fixtures.CHECKER)], input=bridge.encode(candidate), text=True,
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing", result.stdout)


@unittest.skipUnless(fixtures.CHECKER.is_file(), "build tools/lean_boundary to check role layouts")
class RoleLayoutTests(fixtures.SnapshotFixture):
    function_filter = ""

    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.example = Path(temporary.name) / "role_layout.py"
        cls.example.write_text("""# pystachy: dynamic-any
from typing import Any
class Base:
    def __init__(self, value: int) -> None:
        self.value = value
class Role:
    def label(self) -> str:
        return "role"
class Child(Base, Role):
    def label(self) -> str:
        return "child"
def read_role(value: Any) -> str:
    if isinstance(value, Role):
        return value.label()
    return "other"
print(read_role(Child(1)), read_role(Role()))
""")
        super().setUpClass()

    def test_secondary_role_requires_its_physical_prefix(self):
        candidate, metadata = bridge.normalize_snapshot(self.snapshot, "read_role")
        self.assertGreater(metadata["layouts"], 0)
        self.assertTrue(fixtures.ProvedCheckerTests.check(self, candidate))
        snapshot = copy.deepcopy(self.snapshot)
        role = next(entry for entry in snapshot["dynamic_layouts"] if entry["name"] == "Role")
        role["members"].append("str")
        role["llvm"].append("ptr")
        candidate, _ = bridge.normalize_snapshot(snapshot, "read_role")
        self.assertFalse(fixtures.ProvedCheckerTests.check(self, candidate))


@unittest.skipUnless(CLANG, "clang is required for dynamic box ABI correspondence")
class DynamicABI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "runtime.c").read_text()
        cls.declarations = "\n".join(re.search(pattern, source)[0] for pattern in (
            r"struct DynType \{[^\n]+\};", r"struct Dyn \{[^\n]+\};"))

    def offsets(self, declarations):
        declarations = "#include <stdint.h>\n#include <stddef.h>\ntypedef int64_t I;\ntypedef struct Dyn Dyn;\ntypedef struct DynType DynType;\ntypedef struct Str Str;\n" + declarations
        fields = [("box_tag", "Dyn", "t"), ("box_payload", "Dyn", "v"),
                  ("kind", "DynType", "kind"), ("cls", "DynType", "cls"),
                  ("base", "DynType", "base"), ("flags", "DynType", "flags")]
        for name, struct, member in fields:
            declarations += f"\nconst uint64_t abi_{name} = offsetof({struct}, {member});"
        result = subprocess.run([CLANG, "-x", "c", "-S", "-emit-llvm", "-o", "-", "-"],
                                input=declarations, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return {name: int(value) for name, value in re.findall(r"^@abi_(\w+) = .*constant i64 (\d+)", result.stdout, re.M)}

    def test_named_runtime_offsets_and_payload_lowering(self):
        offsets = self.offsets(self.declarations)
        self.assertEqual(offsets, {"box_tag": 0, "box_payload": 8, "kind": 0, "cls": 24, "base": 32, "flags": 40})
        self.assertEqual(int(bridge.CLASS_WORD) * 8, offsets["cls"])
        generated = SimpleNamespace(out=[])
        payload = Ins("dyn.payload", "%slot", "float")
        payload.r, payload.a = [1, 2], [Val("%box", "dyn")]
        gen_lower_ins(generated, None, payload)
        word = re.search(r"getelementptr i64, ptr %box, i64 (\d+)", "\n".join(generated.out))
        self.assertIsNotNone(word)
        self.assertEqual(int(word[1]) * 8, offsets["box_payload"])
        self.assertIn("%t2 = load i64, ptr %t1", "\n".join(generated.out))

    def test_same_width_runtime_field_swaps_change_named_offsets(self):
        original = self.offsets(self.declarations)
        for old, new in (("Str *name; I cls;", "I cls; Str *name;"),
                         ("const DynType *base; I flags;", "I flags; const DynType *base;"),
                         ("const DynType *t; I v;", "I v; const DynType *t;")):
            with self.subTest(old=old):
                changed = self.declarations.replace(old, new)
                self.assertNotEqual(changed, self.declarations)
                self.assertNotEqual(self.offsets(changed), original)


if __name__ == "__main__":
    unittest.main()
