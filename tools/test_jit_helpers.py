"""jit_helpers: which runtime functions the JIT tier's code may inline, and how they are spliced (#705).

The runtime text below is shaped as clang -O2 prints runtime.c's: attribute groups, metadata,
private messages, a static cold failure path, a static variable and named struct types. With
PYSTACHY_TEST_LLVM=<directory of opt> (or opt on PATH), the made module and the spliced program are
verified by opt.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import jit_helpers

RUNTIME = """; ModuleID = 'runtime'
%struct.List = type { i64, i64, ptr, ptr }
%struct.Pair = type { %struct.List, i64 }

@pys_plain = dso_local local_unnamed_addr constant i64 0, align 8
@.str.1 = private unnamed_addr constant [36 x i8] c"IndexError: list index out of range\\00", align 1
@.str.2 = private unnamed_addr constant [43 x i8] c"pystachy: internal error: a global #1 here\\00", align 1
@counter = internal unnamed_addr global i64 0, align 8
@stderr = external local_unnamed_addr global ptr, align 8

; Function Attrs: nounwind uwtable
define dso_local i64 @pys_list_get(ptr nocapture noundef readonly %0, i64 noundef %1) local_unnamed_addr #2 {
  %3 = load i64, ptr %0, align 8, !tbaa !5
  %4 = icmp ult i64 %1, %3
  br i1 %4, label %6, label %5

5:                                                ; preds = %2
  tail call void @pys_fail(ptr noundef nonnull @.str.1) #5
  unreachable

6:                                                ; preds = %2
  %7 = getelementptr inbounds %struct.List, ptr %0, i64 0, i32 2
  %8 = load ptr, ptr %7, align 8, !tbaa !9
  %9 = getelementptr inbounds i64, ptr %8, i64 %1
  %10 = load i64, ptr %9, align 8, !tbaa !10
  ret i64 %10
}

define dso_local double @pys_fdiv(double noundef %0, double noundef %1) local_unnamed_addr #2 {
  %3 = fcmp oeq double %1, 0.000000e+00
  br i1 %3, label %4, label %5

4:
  tail call fastcc void @trap() #6
  unreachable

5:
  %6 = fdiv double %0, %1
  ret double %6
}

define dso_local i64 @pys_pair_len(ptr noundef %0) local_unnamed_addr #2 {
  %2 = getelementptr inbounds %struct.Pair, ptr %0, i64 0, i32 1
  %3 = load i64, ptr %2, align 8
  %4 = load i64, ptr @pys_plain, align 8
  %5 = add i64 %3, %4
  ret i64 %5
}

define dso_local i64 @pys_count() local_unnamed_addr #2 {
  %1 = load i64, ptr @counter, align 8
  %2 = add i64 %1, 1
  store i64 %2, ptr @counter, align 8
  ret i64 %2
}

define dso_local i64 @pys_slow(i64 noundef %0) local_unnamed_addr #3 {
  ret i64 %0
}

define dso_local { i64, i64 } @pys_pair(i64 noundef %0) local_unnamed_addr #2 {
  %2 = insertvalue { i64, i64 } undef, i64 %0, 0
  ret { i64, i64 } %2
}

define internal fastcc void @trap() unnamed_addr #4 {
  %1 = load ptr, ptr @stderr, align 8
  %2 = tail call i32 @fputs(ptr nonnull @.str.2, ptr %1) #6
  tail call void @abort() #5
  unreachable
}

declare dso_local void @pys_fail(ptr noundef) local_unnamed_addr #1
declare noundef i32 @fputs(ptr nocapture noundef readonly, ptr nocapture noundef) local_unnamed_addr #1
declare void @abort() local_unnamed_addr #1

attributes #1 = { noreturn uwtable "no-trapping-math"="true" }
attributes #2 = { nounwind uwtable "min-legal-vector-width"="0" "no-trapping-math"="true" }
attributes #3 = { noinline nounwind uwtable }
attributes #4 = { cold noinline noreturn nounwind uwtable }
attributes #5 = { noreturn }
attributes #6 = { nounwind }

!5 = !{!6, !7, i64 0}
!6 = !{!"List", !7, i64 0}
!7 = !{!"long", !8, i64 0}
!8 = !{!"omnipotent char", !11, i64 0}
!9 = !{!6, !12, i64 16}
!10 = !{!7, !7, i64 0}
!11 = !{!"Simple C/C++ TBAA"}
!12 = !{!"any pointer", !8, i64 0}
"""

PROGRAM = """target triple = "x86_64-unknown-linux-gnu"

declare i64 @pys_list_get(ptr, i64) #0
declare double @pys_fdiv(double, i64)
declare void @pys_fail(ptr)

define i64 @main() {
entry:
  %l = alloca [4 x i64]
  %v = call i64 @pys_list_get(ptr %l, i64 0)
  ret i64 %v
}

attributes #0 = { nounwind }
"""


def opt() -> str:
    # PYSTACHY_TEST_LLVM's opt, which must exist where it is set (a check that it would skip fails
    # instead), else opt on PATH, if any
    d = os.environ.get("PYSTACHY_TEST_LLVM", "")
    if d:
        path = os.path.join(d, "opt")
        if not os.path.exists(path):
            raise RuntimeError(f"PYSTACHY_TEST_LLVM={d} has no opt")
        return path
    return shutil.which("opt") or ""


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.table = jit_helpers.prepare(RUNTIME)
        self.items = {}
        for block in self.table.split("; item ")[1:]:
            head, _, text = block.partition("\n")
            words = head.split(" ")
            self.items[(words[0], words[1])] = (words, text.rstrip("\n"))

    def test_a_small_function_is_copied_available_externally(self):
        words, text = self.items[("helper", "@pys_list_get")]
        self.assertEqual(words[2], "i64(ptr,i64)")
        self.assertTrue(text.startswith("define available_externally i64 @pys_list_get("), text)
        # (attributes in line, no metadata, the struct type spelled as its literal type)
        self.assertIn("nounwind uwtable", text.split("\n")[0])
        self.assertNotIn("#2", text)
        self.assertNotIn("!tbaa", text)
        self.assertIn("getelementptr inbounds { i64, i64, ptr, ptr }, ptr %0", text)
        self.assertIn("@rtj..str.1", text)
        self.assertIn("call void @pys_fail(ptr noundef nonnull @rtj..str.1) noreturn", text)

    def test_its_messages_and_cold_paths_are_private_copies(self):
        _, text = self.items[("const", "@rtj..str.1")]
        self.assertTrue(text.startswith("@rtj..str.1 = private unnamed_addr constant [36 x i8]"), text)
        _, text = self.items[("const", "@rtj..str.2")]
        # (a message's words are its own: "internal" and "#1" in it stay)
        self.assertIn('c"pystachy: internal error: a global #1 here\\00"', text)
        words, text = self.items[("local", "@rtj.trap")]
        self.assertTrue(text.startswith("define internal fastcc void @rtj.trap()"), text)
        self.assertIn("@stderr", words)
        self.assertIn("@rtj..str.2", words)
        words, _ = self.items[("helper", "@pys_fdiv")]
        self.assertIn("@rtj.trap", words)

    def test_the_runtime_s_other_names_are_declared(self):
        _, text = self.items[("decl", "@pys_fail")]
        self.assertEqual(text, "declare void @pys_fail(ptr noundef) local_unnamed_addr noreturn uwtable \"no-trapping-math\"=\"true\"")
        _, text = self.items[("decl", "@pys_plain")]
        self.assertEqual(text, "@pys_plain = external constant i64, align 8")
        _, text = self.items[("decl", "@stderr")]
        self.assertEqual(text, "@stderr = external global ptr, align 8")

    def test_a_nested_struct_type_is_spelled_whole(self):
        _, text = self.items[("helper", "@pys_pair_len")]
        self.assertIn("getelementptr inbounds { { i64, i64, ptr, ptr }, i64 }, ptr %0", text)

    def test_state_noinline_and_aggregates_are_not_copied(self):
        for name in ["@pys_count", "@pys_slow", "@pys_pair"]:
            self.assertNotIn(("helper", name), self.items)
        self.assertNotIn("@counter", self.table)

    def test_the_module_of_every_item_verifies(self):
        tool = opt()
        if not tool:
            self.skipTest("no opt (PYSTACHY_TEST_LLVM)")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "helpers.ll"
            path.write_text(jit_helpers.module(self.table))
            r = subprocess.run([tool, "-passes=verify", "-disable-output", str(path)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


class SpliceTests(unittest.TestCase):
    def setUp(self):
        self.table = jit_helpers.prepare(RUNTIME)

    def test_a_declared_function_of_the_same_signature_is_replaced(self):
        out = jit_helpers.splice(PROGRAM, self.table)
        self.assertNotIn("declare i64 @pys_list_get(ptr, i64) #0", out)
        self.assertIn("define available_externally i64 @pys_list_get(", out)
        self.assertEqual(out.count("@pys_list_get("), 2)  # (its copy, and the call)
        # (its message, once; pys_fail is the program's own declaration)
        self.assertEqual(out.count("@rtj..str.1 = private"), 1)
        self.assertEqual(out.count("declare void @pys_fail("), 1)

    def test_another_signature_keeps_the_declaration(self):
        out = jit_helpers.splice(PROGRAM, self.table)
        self.assertIn("declare double @pys_fdiv(double, i64)", out)
        self.assertNotIn("@rtj.trap", out)

    def test_a_program_that_declares_none_is_unchanged(self):
        program = "define i64 @main() {\nentry:\n  ret i64 0\n}\n"
        self.assertEqual(jit_helpers.splice(program, self.table), program)
        self.assertEqual(jit_helpers.splice(PROGRAM, ""), PROGRAM)
        self.assertEqual(jit_helpers.splice(PROGRAM, "; another table\n"), PROGRAM)

    def test_what_a_copy_needs_is_added_once(self):
        program = PROGRAM.replace("declare double @pys_fdiv(double, i64)", "declare double @pys_fdiv(double, double)")
        out = jit_helpers.splice(program, self.table)
        self.assertIn("define available_externally double @pys_fdiv(", out)
        self.assertEqual(out.count("define internal fastcc void @rtj.trap("), 1)
        self.assertEqual(out.count("@rtj..str.2 = private"), 1)
        self.assertEqual(out.count("@stderr = external global ptr"), 1)
        self.assertEqual(out.count("declare void @abort("), 1)

    def test_the_spliced_program_verifies(self):
        tool = opt()
        if not tool:
            self.skipTest("no opt (PYSTACHY_TEST_LLVM)")
        program = PROGRAM.replace("declare double @pys_fdiv(double, i64)", "declare double @pys_fdiv(double, double)")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "program.ll"
            path.write_text(jit_helpers.splice(program, self.table))
            r = subprocess.run([tool, "-passes=always-inline,cgscc(inline),function(instcombine)", "-S", str(path), "-o", "-"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("call i64 @pys_list_get(", r.stdout)


class TextTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(jit_helpers.tokens('call @a(ptr @"q x", ptr @a.b) %t.1 %0', "@"), ["@a", '@"q x"', "@a.b"])
        self.assertEqual(jit_helpers.rename("@a @ab @a.b %a", {"@a": "@z", "%a": "%y"}), "@z @ab @a.b %y")

    def test_signature(self):
        self.assertEqual(jit_helpers.signature("declare noalias ptr @f(ptr nocapture, i64 noundef) #3"), "ptr(ptr,i64)")
        self.assertEqual(jit_helpers.signature("define dso_local void @f() #3 {"), "void()")
        self.assertEqual(jit_helpers.signature("declare { i64, i64 } @f(i64)"), "")
        self.assertEqual(jit_helpers.signature("declare i64 @f(%struct.X)"), "")


if __name__ == "__main__":
    unittest.main()
