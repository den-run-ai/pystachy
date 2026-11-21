"""A module printed at the lowering boundary compiles to the LLVM module the compiler emits.

tools/typed_ir_text.py's module text holds what LLVM lowering reads (docs/typed-ir.md, "Text
form"). Each program of SAMPLE is inspected, its typed-after module printed, parsed back and
compiled with the compiler's own lowering (compile_module), and the LLVM must equal what the
compiler emitted in that inspection, byte for byte. The sample covers classes, closures,
generators, exceptions, unions, dynamic Any, promoting ints, tuples returned by value, closed
recursion, the key kinds of empty dicts and sets, object dispatchers and C externs.

Run with python3 -m unittest discover -s tools -p test_typed_ir_compile.py.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import typed_ir_text as text

ROOT = Path(__file__).resolve().parent.parent
TOOL = [sys.executable, str(ROOT / "tools/typed_ir_text.py")]
# each program and what its module shows of lowering's state (features)
SAMPLE = {
    "tests/programs/classes/inheritance_secondary.py": {"classes", "dynamic", "objects"},
    "tests/programs/classes/inheritance_union_family.py": {"unions", "closed", "tupleret", "exceptions"},
    "tests/programs/classes/init_closure_field.py": {"closures", "methods"},
    "tests/programs/generators/gen_close.py": {"generators", "exceptions"},
    "tests/programs/generators/gen_protocol_gc.py": {"generators", "protocol"},
    "tests/programs/exceptions/exc_as_rebind.py": {"exceptions"},
    "tests/programs/inference/dynany_generator_channel_protocol.py": {"dynamic", "drops"},
    "tests/programs/classes/cmp_notimplemented_enum_big.py": {"promoting", "templates"},
    "tests/programs/containers/tuples_and_classes.py": {"tupleret", "constants"},
    "tests/programs/containers/empty_containers.py": {"keykinds"},
    "tests/programs/generics/template_empty_forward.py": {"built", "descriptors"},
    "tests/programs/classes/dataclass_hash_keys.py": {"hashed", "objects"},
    "tests/ffi/c_ctypes_bytes.py": {"externs"},
}


def features(module):
    """What a module record shows of the state that lowering reads."""
    a = module["attributes"]
    ops = {i["op"] for r in module["functions"] for b in r["blocks"] for i in b["operations"]}
    attributes = [r["attributes"] for r in module["functions"]]
    kinds = [k["kind"] + k["built"] for k in module["key_kinds"]]
    found = {
        "classes": any(c["fields"] and not c["template"] for c in module["classes"].values()),
        "templates": any(c["template"] for c in module["classes"].values()),
        "methods": any(f["class"] != "" for f in attributes),
        "closures": "icall" in ops,
        "generators": any(r["coroutine"] for r in module["functions"]),
        "drops": "gen.drop" in ops,
        "exceptions": "landing" in ops,
        "unions": any(op.startswith("union.") for op in ops),
        "dynamic": a["dynamic"], "promoting": a["promoting"], "protocol": a["protocol"],
        "tupleret": any(f["tupleret"] > 0 for f in attributes) and any(f["tuplecalls"] for f in attributes),
        "closed": any(f["closed"] and f["rdepth"] != "" for f in attributes),
        "constants": any(c["kind"] == "tuple" for c in module["constants"]),
        "keykinds": any(k["kind"] != "" for k in module["key_kinds"]),
        "built": any(k["built"] != "" for k in module["key_kinds"]),
        "descriptors": any("ptrtoint" in k for k in kinds),
        "objects": len(a["objects"]) > 0, "hashed": len(a["hashed"]) > 0,
        "externs": any(x["c"] for x in module["externs"]),
    }
    return {name for name, present in found.items() if present}


class RoundTripTests(unittest.TestCase):
    """Print, parse, compile, compare: the module text is complete for lowering."""

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix=".typed-ir-compile-")
        cls.inspections = {}
        for program in SAMPLE:
            directory = Path(cls.directory.name) / program.replace("/", "_")
            directory.mkdir()
            cls.inspections[program] = text.inspected(ROOT / program, directory)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def module(self, program):
        report, snapshot, llvm = self.inspections[program]
        self.assertEqual(report["status"], "ok", report["diagnostics"])
        return text.module_from_snapshot(snapshot), llvm

    def test_each_programs_module_compiles_to_the_compilers_llvm(self):
        covered = set()
        for program, expected in SAMPLE.items():
            with self.subTest(program=program):
                module, llvm = self.module(program)
                self.assertEqual(text.refusals(module), [])
                written = text.format_module(module)
                parsed = text.parse_module(written)
                self.assertEqual(text.format_module(parsed), written)
                lowered = text.compile_module(parsed)
                self.assertTrue(lowered == llvm, text.first_difference(llvm, lowered) if lowered != llvm else "")
                found = features(parsed)
                self.assertLessEqual(expected, found)
                covered |= found
        self.assertEqual(covered, {"classes", "templates", "methods", "closures", "generators", "drops", "exceptions", "unions",
                                   "dynamic", "promoting", "protocol", "tupleret", "closed", "constants", "keykinds", "built",
                                   "descriptors", "objects", "hashed", "externs"})

    def test_compile_mode_writes_the_compilers_llvm(self):
        program = "tests/programs/classes/inheritance_union_family.py"
        module, llvm = self.module(program)
        with tempfile.TemporaryDirectory() as directory:
            listing, output = Path(directory) / "module.tir", Path(directory) / "module.ll"
            listing.write_text(text.format_module(module, True), encoding="utf-8")
            checked = subprocess.run(TOOL + ["check", str(listing)], capture_output=True, text=True, timeout=120)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            compiled = subprocess.run(TOOL + ["compile", str(listing), "-o", str(output)], capture_output=True, text=True, timeout=120)
            self.assertEqual((compiled.returncode, compiled.stderr), (0, ""))
            self.assertEqual(output.read_bytes(), llvm.encode("latin-1"))
            # (standard output, where no -o names a file)
            printed = subprocess.run(TOOL + ["compile", str(listing)], capture_output=True, timeout=120)
            self.assertEqual(printed.stdout, llvm.encode("latin-1"))

    def test_state_left_out_of_the_text_changes_the_llvm(self):
        # (each of these is state lowering reads: without it, the module compiles to other LLVM,
        # which the round trip finds, or is refused)
        module, llvm = self.module("tests/programs/classes/inheritance_union_family.py")
        written = text.format_module(module)
        for what, change in (("a runtime declaration", lambda m: m["runtime"].pop()),
                             ("a string constant", lambda m: m["constants"].pop(0)),
                             ("a global", lambda m: m["globals"].pop()),
                             ("a class's struct", lambda m: m["classes"][next(c for c in m["classes"] if m["classes"][c]["fields"])]["fields"].pop()),
                             ("closed recursion", lambda m: [r["attributes"].update(closed=False) for r in m["functions"]]),
                             ("tuples returned by value", lambda m: [r["attributes"].update(tuplecalls=[]) for r in m["functions"]]),
                             ("an option", lambda m: m["attributes"]["opts"].remove("fieldtbaa"))):
            with self.subTest(what=what):
                changed = text.parse_module(written)
                change(changed)
                try:
                    lowered = text.compile_module(text.parse_module(text.format_module(changed)))
                except text.TextError:
                    continue
                self.assertNotEqual(lowered, llvm)

    def test_a_module_without_lowerings_state_is_refused(self):
        module, _ = self.module("tests/programs/exceptions/exc_as_rebind.py")
        for change, expected in (
                (lambda a: a.update(complete=False), "does not declare the state that lowering reads"),
                (lambda a: a.update(extension="fast"), "extension module fast (pystachy ext"),
                (lambda a: a.update(rtmode=True), "runtime.py's module (pystachy rt"),
                (lambda a: a.update(debuglines=True), "LLVM line tables (PYSTACHY_DEBUG_LINES=1"),
                (lambda a: a["unsupported"].append("something new"), "something new")):
            with self.subTest(expected=expected):
                changed = json.loads(json.dumps(module))
                change(changed["attributes"])
                self.assertTrue(any(expected in problem for problem in text.refusals(changed)), text.refusals(changed))
                with self.assertRaisesRegex(text.TextError, "cannot compile the module: .*" + expected.replace("(", r"\(")):
                    text.compile_module(changed)
        # (a module written by hand declares none of lowering's state: a module's functions alone
        # print, but do not compile)
        with self.assertRaisesRegex(text.TextError, "does not declare the state that lowering reads"):
            text.compile_module(text.parse_module("module {\n}\n"))
        # (a snapshot of some functions, --function, compiles none of them)
        report, snapshot, _ = self.inspections["tests/programs/exceptions/exc_as_rebind.py"]
        some = dict(snapshot, functions=snapshot["functions"][:1])
        self.assertTrue(any("functions" in problem for problem in text.refusals(text.module_from_snapshot(some))))

    def test_compile_rejects_what_lowering_cannot_take(self):
        module, _ = self.module("tests/programs/containers/empty_containers.py")
        for change, expected in ((lambda m: m["runtime"].append({"key": "no.such"}), "runtime no.such: no RUNTIME entry"),
                                 (lambda m: m["runtime_data"].append({"symbol": "pys_none"}), "rtdata pys_none: no RTDATA entry"),
                                 (lambda m: m["holes"].pop(0), "holes are numbered from 1, in order")):
            with self.subTest(expected=expected):
                changed = json.loads(json.dumps(module))
                change(changed)
                with self.assertRaisesRegex(text.TextError, expected):
                    text.compile_module(changed)


class LoweringTextTests(unittest.TestCase):
    """The declarations and attributes that hold lowering's state print and read back."""

    MODULE = """module complete opts=[fieldtbaa tupleret] exceptions protocol dynamic promoting plain=[gen[int]] untracked=[m] objects=[Point:0 "odd name":1] compared=[Point] hashed=[Point] unequal=[Point] crossed=["odd name"] {
  class Point tagged fields=[" class":int x:int] module=m
  class Box template exception=ValueError
  class "odd name"
  hole 1 type=dict[str,int]
  hole 2
  global @g.p type=Point
  global @g.n type=int
  root @g.p
  root "getelementptr inbounds ({i64, ptr}, ptr @g.big, i32 0, i32 1)"
  const @s.0 kind=string text=" "
  const @s.1 kind=string
  const @tc.0 kind=tuple text=tuple[int,str] refs=["" ""] items=(int 1, str @s.0)
  const @dt.Point kind=dyntype refs=[@s.0 @s.1 null] items=(int 8, int 0, int 0)
  runtime list.append
  runtime write
  rtdata pys_dyn_none_box
  extern @f.c_puts symbol=@f.c_puts params=[str] result=int c csym=@puts library=libc.so.6 ctypes=[str] cret=c_int
  extern @f.provided symbol=@f.provided params=[int int] result=None provided
  keykind dict[str,int] kind=1
  keykind set[tuple[int,int]] kind="ptrtoint (ptr @s.1 to i64)" built="ptrtoint (ptr getelementptr (i8, ptr @s.1, i64 2) to i64)"
}

function @f.go(n: int) -> int effects=R name=go class=Point decorator=staticmethod nullable module=m home=n kind=lambda export pyexport extern gret=dyn rdepth=%t3 casts=[4 9] closed tupleret=2 tupleconst tuplecalls=[%t5 %t7] {
entry:
  ret(int %a0)
}
"""

    def test_a_written_module_with_every_declaration_reads_and_prints_unchanged(self):
        module = text.parse_module(self.MODULE)
        self.assertEqual(text.format_module(module), self.MODULE)
        self.assertEqual(text.module_roundtrip_errors(module), [])
        self.assertEqual(module["attributes"]["objects"], {"Point": 0, "odd name": 1})
        self.assertEqual(module["attributes"]["crossed"], ["odd name"])
        self.assertEqual(module["holes"], [{"number": "1", "type": "dict[str,int]"}, {"number": "2", "type": ""}])
        self.assertEqual(module["roots"][1]["value"], "getelementptr inbounds ({i64, ptr}, ptr @g.big, i32 0, i32 1)")
        self.assertEqual(module["constants"][2], {"name": "@tc.0", "kind": "tuple", "text": "tuple[int,str]", "refs": ["", ""],
                                                  "items": [{"value": "1", "type": "int"}, {"value": "@s.0", "type": "str"}]})
        self.assertEqual(module["constants"][1], {"name": "@s.1", "kind": "string", "text": "", "refs": [], "items": []})
        self.assertEqual(module["externs"][1], {"key": "@f.provided", "symbol": "@f.provided", "params": ["int", "int"], "result": "None",
                                                "provided": True, "c": False, "csym": "", "library": "", "ctypes": [], "cret": "",
                                                "at": False, "direct": False, "declare": False, "dynamic": False, "narrow": False})
        self.assertEqual(module["classes"]["Box"]["template"], True)
        self.assertEqual(module["classes"]["Box"]["exception"], "ValueError")
        attributes = module["functions"][0]["attributes"]
        self.assertEqual(attributes, {"name": "go", "class": "Point", "decorator": "staticmethod", "nullable": True, "module": "m",
                                      "home": "n", "kind": "lambda", "export": True, "pyexport": True, "extern": True, "gret": "dyn",
                                      "rdepth": "%t3", "casts": [4, 9], "closed": True, "tupleret": 2, "tupleconst": True,
                                      "tuplecalls": ["%t5", "%t7"]})
        # (the function's FnInfo and IFn hold its attributes, and give them back)
        fn = text.to_ifn(module["functions"][0])
        self.assertEqual((fn.f.name, fn.f.cls, fn.f.deco, fn.f.node.kind, fn.rdepth, fn.casts, fn.n), ("go", "Point", "staticmethod", "lambda", "%t3", [4, 9], 9))
        self.assertEqual(text.function_attributes(fn), dict(attributes, closed=False, tupleret=0, tupleconst=False, tuplecalls=[]))
        # (each string a constant may hold: its characters are its bytes)
        every = {"name": "@s.9", "kind": "string", "text": "".join(chr(c) for c in range(256)), "refs": [], "items": []}
        line = text.declaration_text("const", "@s.9", every)
        self.assertEqual(text.read_declaration(line)[2], every)

    def test_malformed_declarations_are_rejected_with_their_line(self):
        for old, new, expected in (
                ("  global @g.n type=int\n", "  global @g.n\n", "line 8: global @g.n needs type="),
                ("  root @g.p\n", "  root @g.p type=x\n", "line 9: unknown root field 'type'"),
                ("  hole 2\n", "  hole 2 type=\"\"\n", "line 6: hole field type is omitted where it holds its default"),
                ("items=(int 1, str @s.0)", "items=(int 1 str @s.0)", "line 13: expected ', '"),
                ("items=(int 1, str @s.0)", "items=()", "line 13: expected an atom"),
                (" c csym=@puts", " c=1 csym=@puts", "line 18: extern field c is a flag, written bare"),
                ("  runtime write\n", "  runtime write\n  runtime write\n", "line 17: runtime write is declared twice"),
                ("  global @g.p type=Point\n", "  global @g.p type=Point\n  hole 3\n", "line 8: a hole after the globals"),
                ("module complete opts", "module complete complete opts", "line 1: module field complete is repeated"),
                ("module complete opts", "module opts=[x] complete opts", "line 1: module field complete must come before opts"),
                ("module complete opts", "module sort=1 opts", "line 1: unknown module field 'sort'"),
                ("module complete opts", "module complete=1 opts", "line 1: module field complete is a flag, written bare"),
                ("objects=[Point:0", "objects=[Point:x", "line 1: objects=[ needs an integer after Point:")):
            with self.subTest(expected=expected):
                changed = self.MODULE.replace(old, new, 1)
                self.assertNotEqual(changed, self.MODULE)
                with self.assertRaises(text.TextError) as raised:
                    text.parse(changed)
                self.assertIn(expected, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
