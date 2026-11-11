"""The runtime facts both dynamic payload checkers trust, against runtime.c's definitions.

The compiler's proof (src/pystachy_compiler/dynamic_proof.py) and the Lean bridge
(tools/check_lean_boundary.py) each copy runtime.c's DynType kinds and role flag, its builtin
DynTypes, the word of a DynType that holds its class number and its constant boxes; dynamic.py
emits DynTypes with the same kinds and flags. These tests read those definitions from runtime.c,
so that neither copy can drift from the runtime. They check no layout beyond them.
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import check_lean_boundary as bridge  # noqa: E402
from src.pystachy_compiler import dynamic, dynamic_proof  # noqa: E402
from src.pystachy_compiler.utils import ListLayout  # noqa: E402


class RuntimeTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "runtime.c").read_text()
        kinds = re.search(r"enum \{ (DK_NONE\b[^}]*)\}", source)[1]
        cls.kinds = {name.strip(): value for value, name in enumerate(kinds.split(","))}
        flags = re.search(r"enum \{ (DF_EQ\b[^}]*)\}", source)[1]
        cls.flags = {name.strip(): int(value) for name, value in (item.split("=") for item in flags.split(","))}
        # each builtin DynType: its kind and descriptor (a DTYPE, or bigint's own initializer)
        cls.builtins = {"@" + name: (cls.kinds[kind], descriptor) for name, kind, descriptor in
                        re.findall(r"DTYPE\((pys_dyntype_\w+), (DK_\w+), (\w+), \w+\)", source)}
        for name, kind, descriptor in re.findall(r"const DynType (pys_dyntype_\w+) = \{(DK_\w+), \(Str \*\)&(\w+),",
                                                 source):
            cls.builtins["@" + name] = (cls.kinds[kind], descriptor)
        fields = re.search(r"struct DynType \{([^}]*)\};", source)[1]
        cls.fields = [field.strip() for field in fields.split(";") if field.strip()]
        cls.boxes = {"@" + box: ("@" + tag, int(payload)) for box, tag, payload in
                     re.findall(r"(pys_dyn_\w+_box) = \{&(pys_dyntype_\w+), (\d+)\}", source)}

    def test_parsed_runtime_definitions(self):
        # (guards against a regular expression that silently matches less of runtime.c)
        self.assertEqual(self.kinds["DK_NONE"], 0)
        self.assertGreaterEqual(len(self.kinds), 13)
        self.assertEqual(self.flags["DF_EQ"], 1)
        self.assertIn("@pys_dyntype_bigint", self.builtins)
        self.assertGreaterEqual(len(self.builtins), 12)
        self.assertEqual(len(self.boxes), 3)

    def test_kinds_and_flags(self):
        for module in (dynamic_proof, bridge, dynamic):
            for name in dir(module):
                if name.startswith("DK_") or name.startswith("DF_"):
                    with self.subTest(module=module.__name__, name=name):
                        table = self.kinds if name.startswith("DK_") else self.flags
                        self.assertEqual(getattr(module, name), table[name])

    def test_builtin_dyntypes(self):
        runtime = {name: kind for name, (kind, _) in self.builtins.items()}
        self.assertEqual(dynamic_proof.BUILTIN_KINDS, runtime)
        self.assertEqual(bridge.BUILTIN_TYPES, runtime)

    def test_class_number_word(self):
        # every field before cls is one i64 word: an I or a pointer
        index = next(j for j, field in enumerate(self.fields) if field.split()[-1].lstrip("*") == "cls")
        self.assertTrue(all(field.startswith("I ") or "*" in field for field in self.fields[:index]), self.fields)
        self.assertEqual(int(dynamic_proof.CLASS_WORD), index)
        self.assertEqual(int(bridge.CLASS_WORD), index)

    def test_constant_boxes(self):
        self.assertEqual(dynamic_proof.BOX_TAGS, {box: tag for box, (tag, _) in self.boxes.items()})
        # a bool's payload is its int value, which an int read takes
        self.assertEqual(self.boxes["@pys_dyn_true_box"], ("@pys_dyntype_bool", 1))
        self.assertEqual(self.boxes["@pys_dyn_false_box"], ("@pys_dyntype_bool", 0))

    def test_builtin_payload_layouts(self):
        tables = {t: sorted(tags) for t, tags in bridge.BUILTIN_PAYLOADS.items()}
        self.assertEqual(dynamic_proof.BUILTIN_PAYLOADS, tables)
        for t, tags in dynamic_proof.BUILTIN_PAYLOADS.items():
            with self.subTest(t=t):
                self.assertEqual(tags, sorted(set(tags)))
                self.assertTrue(set(tags) <= set(self.builtins))
        # the DynTypes of the boxes dynamic.py makes of each builtin type are among those its read takes
        for t, name in dynamic.BUILTIN.items():
            if t != "None":
                self.assertIn("@" + name, dynamic_proof.BUILTIN_PAYLOADS[t])
        for t in ("list[dyn]", "list[int]"):
            for promoting in (False, True):
                self.assertIn("@" + ListLayout(t, promoting).dynamic_type, dynamic_proof.BUILTIN_PAYLOADS[t])
        # checked and promoting int lists share one payload layout: one descriptor
        intlists = {self.builtins[tag][1] for tag in dynamic_proof.BUILTIN_PAYLOADS["list[int]"]}
        self.assertEqual(len(intlists), 1)


if __name__ == "__main__":
    unittest.main()
