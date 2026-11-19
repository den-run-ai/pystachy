"""runtime.c's list accesses carry the TBAA tags that compiled code gives the same memory.

The driver rewrites clang's access tags through struct List and struct Slot as lowering's "@list"
and "@slot" tags (driver.retag_runtime_lists) in the file clang writes (driver.retag_runtime_file).
The default suite checks the rewrite on small IR and the file step's outcomes.
Set PYSTACHY_TEST_LLVM to a toolchain directory to compile runtime.c as the driver does, check
that clang still names both struct types, and assemble the retagged module.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pystachy_compiler import driver

ROOT = Path(__file__).resolve().parents[1]
CLANG_IR = """define void @f(ptr %l, ptr %t) {
  %n = load i64, ptr %l, align 8, !tbaa !5
  %a = getelementptr inbounds i8, ptr %l, i64 16
  %p = load ptr, ptr %a, align 8, !tbaa !6
  store i64 %n, ptr %p, align 8, !tbaa !8
  %c = getelementptr inbounds i8, ptr %l, i64 8
  store i64 0, ptr %c, align 8, !tbaa !11
  store i64 1, ptr %t, align 8, !tbaa !10
  ret void
}
!0 = !{!"Simple C/C++ TBAA"}
!1 = !{!"omnipotent char", !0, i64 0}
!2 = !{!"long", !1, i64 0}
!3 = !{!"any pointer", !1, i64 0}
!4 = !{!"List", !2, i64 0, !2, i64 8, !3, i64 16, !3, i64 24}
!5 = !{!4, !2, i64 0}
!6 = !{!4, !3, i64 16}
!7 = !{!"Slot", !2, i64 0}
!8 = !{!7, !2, i64 0}
!9 = !{!"", !4, i64 0, !3, i64 32}
!10 = !{!9, !2, i64 0}
!11 = !{!4, !2, i64 8, i64 1}
"""


def node(text, n):
    """The operands of metadata node !n of text, as written."""
    m = re.search(rf"^!{n} = !{{(.*)}}$", text, re.M)
    return m.group(1) if m else None


def base_name(text, tag):
    """The name of the struct type that access tag !tag's base names, and its root's name."""
    ops = node(text, tag).split(", ")
    typ = node(text, ops[0][1:]).split(", ")
    scalar = node(text, ops[1][1:]).split(", ")
    root = node(text, scalar[1][1:])
    return typ[0].strip('!"'), root.strip('!"'), int(ops[2][4:])


class Retag(unittest.TestCase):
    def test_list_and_slot_tags_become_lowerings(self):
        out = driver.retag_runtime_lists(CLANG_IR)
        self.assertEqual(base_name(out, 5), ("@list", "pystachy fields", 0))
        self.assertEqual(base_name(out, 6), ("@list", "pystachy fields", 16))
        self.assertEqual(base_name(out, 8), ("@slot", "pystachy fields", 0))
        self.assertEqual(base_name(out, 11), ("@list", "pystachy fields", 8))
        self.assertTrue(node(out, 11).endswith(", i64 1"), "a constant flag stays")
        # an item and the items pointer have the scalar types lowering gives them
        self.assertEqual(node(out, node(out, 8).split(", ")[1][1:]).split(", ")[0], '!"int"')
        self.assertEqual(node(out, node(out, 6).split(", ")[1][1:]).split(", ")[0], '!"pointer"')

    def test_other_tags_and_types_keep_clangs(self):
        out = driver.retag_runtime_lists(CLANG_IR)
        self.assertEqual(node(out, 10), "!9, !2, i64 0")  # a struct that holds a List keeps clang's tag
        self.assertEqual(node(out, 9), '!"", !4, i64 0, !3, i64 32')
        self.assertEqual(node(out, 4), '!"List", !2, i64 0, !2, i64 8, !3, i64 16, !3, i64 24')
        self.assertIn("define void @f(ptr %l, ptr %t) {", out)

    def test_lowerings_nodes(self):
        # the nodes lower_module's tbaa_nodes emits for "@list" and "@slot", so that llvm-link
        # unites them with the program's
        out = driver.retag_runtime_lists(CLANG_IR)
        lst = node(out, node(out, 5).split(", ")[0][1:]).split(", ")
        self.assertEqual(lst[0], '!"@list"')
        self.assertEqual([lst[i] for i in (2, 4, 6, 8)], ["i64 0", "i64 8", "i64 16", "i64 24"])
        self.assertEqual(lst[1], lst[3])
        self.assertEqual(lst[5], lst[7])
        slot = node(out, node(out, 8).split(", ")[0][1:]).split(", ")
        self.assertEqual(slot, ['!"@slot"', lst[1], "i64 0"])

    def test_ir_without_either_type_is_unchanged(self):
        text = CLANG_IR.replace('!"List"', '!"Other"').replace('!"Slot"', '!"Another"')
        self.assertEqual(driver.retag_runtime_lists(text), text)


class RetagFile(unittest.TestCase):
    # driver.retag_runtime_file: the runtime build's step between clang and llvm-as
    def test_file_is_rewritten_in_place(self):
        with tempfile.TemporaryDirectory(prefix="pystachy-list-tags-") as tmp:
            path = Path(tmp) / "runtime-s.ll"
            path.write_text(CLANG_IR, encoding="latin-1")
            self.assertEqual(driver.retag_runtime_file(str(path)), 0)
            self.assertEqual(path.read_text(encoding="latin-1"), driver.retag_runtime_lists(CLANG_IR))

    def test_missing_file_is_left_for_llvm_as(self):
        with tempfile.TemporaryDirectory(prefix="pystachy-list-tags-") as tmp:
            path = Path(tmp) / "runtime-s.ll"
            self.assertEqual(driver.retag_runtime_file(str(path)), 0)
            self.assertFalse(path.exists(), "no file is made where clang wrote none")

    def test_failed_write_fails_the_build(self):
        real = open

        def read_only(name, mode="r", *args, **kwargs):
            if "w" in mode:
                raise OSError("no space left on device")
            return real(name, mode, *args, **kwargs)
        with tempfile.TemporaryDirectory(prefix="pystachy-list-tags-") as tmp:
            path = Path(tmp) / "runtime-s.ll"
            path.write_text(CLANG_IR, encoding="latin-1")
            with patch("builtins.open", read_only):
                self.assertEqual(driver.retag_runtime_file(str(path)), 1)


LLVM = os.environ.get("PYSTACHY_TEST_LLVM", "")


@unittest.skipUnless(LLVM, "set PYSTACHY_TEST_LLVM to compile runtime.c")
class RuntimeC(unittest.TestCase):
    def test_runtime_c_names_both_types_and_assembles_retagged(self):
        tools = LLVM.rstrip("/") + "/"
        with tempfile.TemporaryDirectory(prefix="pystachy-list-tags-") as tmp:
            ll = Path(tmp) / "runtime.ll"
            subprocess.run([tools + "clang", "-O2", "-S", "-emit-llvm", "-x", "c", str(ROOT / "runtime.c"),
                            "-o", str(ll), "-fexceptions", "-Wno-unused-command-line-argument"], check=True)
            text = ll.read_text(encoding="latin-1")
            self.assertIn('= !{!"List", ', text, "runtime.c's List must stay a named struct (struct List)")
            self.assertIn('= !{!"Slot", ', text, "runtime.c's Slot must stay a named struct (struct Slot)")
            out = driver.retag_runtime_lists(text)
            ids = {m.group(1) for m in re.finditer(r'^!(\d+) = !{!"(?:List|Slot)", ', out, re.M)}
            through = [m.group(0) for m in re.finditer(r"^!\d+ = !{!(\d+), ", out, re.M) if m.group(1) in ids]
            self.assertEqual(through, [], "every access tag through List or Slot is lowering's")
            self.assertGreater(len(re.findall(r'!{!"@slot", ', out)), 0)
            (Path(tmp) / "retagged.ll").write_text(out, encoding="latin-1")
            subprocess.run([tools + "llvm-as", str(Path(tmp) / "retagged.ll"), "-o", os.devnull], check=True)


if __name__ == "__main__":
    unittest.main()
