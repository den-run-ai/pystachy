"""The AOT tier's precompiled runtime (src/pystachy_compiler/aot_runtime.py, #706).

split() turns the runtime's optimized module into the object's module, whose local symbols become
hidden external ones, and the interface each program is optimized against: available_externally
bodies of small functions and of functions that switch on a parameter, declarations of the rest,
no constructors. With LLVM (PYSTACHY_CACHE_TEST_LLVM, PYSTACHY_LLVM or PATH), both views must
verify, and a static that an inlined body and the runtime's own code update must stay one
variable in the executable.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler.aot_runtime import BODY, split  # noqa: E402


def body(n):
    # n instructions that keep a value alive to the return
    lines = ["  %v0 = add i64 %0, 1"]
    lines += [f"  %v{i} = add i64 %v{i - 1}, {i}" for i in range(1, n - 1)]
    return lines + [f"  ret i64 %v{n - 2}"]


MODULE = "\n".join([
    "@counter = internal global i64 0, align 8",
    "@table = private unnamed_addr constant [2 x i64] [i64 1, i64 2], align 8",
    "@pys_plain = local_unnamed_addr constant i64 1, align 8",
    "@pys_fl = dso_local global [2 x ptr] zeroinitializer, align 16",
    "@stderr = external local_unnamed_addr global ptr, align 8",
    "@__libc_hook = extern_weak global ptr, align 8",
    "@llvm.global_ctors = appending global [1 x { i32, ptr, ptr }] [{ i32, ptr, ptr } { i32 65535, ptr @init, ptr null }]",
    "",
    "define internal fastcc i64 @bump() unnamed_addr #0 {",
    "  %v = load i64, ptr @counter, align 8",
    "  %w = add i64 %v, 1",
    "  store i64 %w, ptr @counter, align 8",
    "  ret i64 %w",
    "}",
    "",
    "define dso_local i64 @pys_small(i64 noundef %0) local_unnamed_addr #0 {",
    "  %a = call fastcc i64 @bump()",
    "  %b = add i64 %a, %0",
    "  ret i64 %b",
    "}",
    "",
    "define dso_local i64 @pys_big(i64 noundef %0) local_unnamed_addr #0 !func_sanitize !0 {",
    *body(BODY + 1),
    "}",
    "",
    "define dso_local i64 @pys_switch(i64 noundef %0, i64 noundef %1) local_unnamed_addr #0 {",
    "  switch i64 %1, label %other [",
    "    i64 0, label %zero",
    "  ]",
    "",
    "zero:",
    "  ret i64 0",
    "",
    "other:",
    *body(BODY + 1)[:-1],
    f"  ret i64 %v{BODY - 1}",
    "}",
    "",
    "define dso_local i64 @pys_forced(i64 noundef %0) local_unnamed_addr #2 {",
    *body(BODY + 1),
    "}",
    "",
    "$pys_grouped = comdat any",
    "define dso_local i64 @pys_grouped(i64 noundef %0) local_unnamed_addr #0 comdat {",
    "  ret i64 %0",
    "}",
    "",
    "define weak i64 @pys_hook(i64 noundef %0) #0 {",
    "  ret i64 %0",
    "}",
    "",
    "define dso_local noalias nonnull ptr @pys_new(i64 noundef %0) local_unnamed_addr #1 {",
    "  %p = load ptr, ptr @pys_fl, align 16",
    "  ret ptr %p",
    "}",
    "",
    "define internal void @init() {",
    "  store i64 0, ptr @counter, align 8",
    "  ret void",
    "}",
    "",
    "declare void @abort() local_unnamed_addr",
    "",
    "attributes #0 = { nounwind }",
    "attributes #1 = { noinline nounwind }",
    "attributes #2 = { alwaysinline nounwind }",
    "",
    "!0 = !{i32 -1056584962, i32 0}",
    "",
])


def defines(text, name):
    return [line for line in text.split("\n") if line.startswith(("define ", "declare ")) and f"@{name}(" in line]


class Split(unittest.TestCase):
    def test_views(self):
        obj, face, new = split(MODULE, BODY)
        # the object: local symbols hidden external, everything else as it was
        self.assertEqual(defines(obj, "bump"), ["define hidden fastcc i64 @bump() unnamed_addr #0 {"])
        self.assertIn("@counter = hidden global i64 0, align 8", obj)
        self.assertIn("@table = hidden unnamed_addr constant [2 x i64] [i64 1, i64 2], align 8", obj)
        self.assertIn("@llvm.global_ctors = appending global", obj)
        self.assertEqual(defines(obj, "pys_hook"), ["define weak i64 @pys_hook(i64 noundef %0) #0 {"])
        # the interface: small functions' and dispatchers' bodies, declarations of the rest
        self.assertEqual(defines(face, "bump"), ["define available_externally hidden fastcc i64 @bump() unnamed_addr #0 {"])
        self.assertEqual(defines(face, "pys_small"), ["define available_externally dso_local i64 @pys_small(i64 noundef %0) local_unnamed_addr #0 {"])
        self.assertEqual(defines(face, "pys_big"), ["declare dso_local i64 @pys_big(i64 noundef %0) local_unnamed_addr #0"],
                         "a declaration carries no metadata attachment (UBSan's !func_sanitize)")
        self.assertEqual(defines(face, "pys_switch"), ["define available_externally dso_local i64 @pys_switch(i64 noundef %0, i64 noundef %1) local_unnamed_addr #0 {"])
        self.assertEqual(defines(face, "pys_hook"), ["declare i64 @pys_hook(i64 noundef %0) #0"], "a weak definition is never inlined")
        self.assertEqual(defines(face, "pys_forced"), ["define available_externally dso_local i64 @pys_forced(i64 noundef %0) local_unnamed_addr #2 {"],
                         "alwaysinline keeps its body, whatever its size")
        self.assertEqual(defines(face, "pys_grouped"), ["define available_externally dso_local i64 @pys_grouped(i64 noundef %0) local_unnamed_addr #0 {"],
                         "the interface puts nothing in a comdat")
        self.assertIn("@__libc_hook = extern_weak global ptr, align 8", face)
        self.assertIn("@counter = available_externally hidden global i64 0, align 8", face)
        self.assertIn("@pys_plain = available_externally local_unnamed_addr constant i64 1, align 8", face)
        self.assertIn("@stderr = external local_unnamed_addr global ptr, align 8", face)
        self.assertNotIn("llvm.global_ctors", face, "the object runs the runtime's constructors, once")
        self.assertEqual(new, "declare dso_local noalias nonnull ptr @pys_new(i64 noundef %0) local_unnamed_addr #1")

    def test_body_bound(self):
        self.assertEqual(len(defines(split(MODULE, BODY + 1)[1], "pys_big")[0].split("{")), 2, "within the bound: a body")
        self.assertTrue(defines(split(MODULE, BODY)[1], "pys_big")[0].startswith("declare "))

    def test_replaceable_data(self):
        # data that another definition may replace (a weak global) has no safe interface
        self.assertEqual(split(MODULE.replace("@pys_plain = local_unnamed_addr", "@pys_plain = weak local_unnamed_addr"), BODY), [])

    def test_unnamed_definitions(self):
        # a global or function named by number cannot be a hidden symbol under that name
        # (driver.aot_build's name-anon-globals names them first)
        self.assertEqual(split(MODULE.replace("@table = private", "@0 = private"), BODY), [])
        self.assertEqual(split(MODULE.replace("define internal void @init()", "define internal void @7()"), BODY), [])
        self.assertNotEqual(split(MODULE.replace("@table = private", "@t0 = private"), BODY), [])


def llvm():
    for directory in (os.environ.get("PYSTACHY_CACHE_TEST_LLVM", ""), os.environ.get("PYSTACHY_LLVM", "")):
        if directory and all((Path(directory) / tool).exists() for tool in ("clang", "opt", "llvm-link")):
            return Path(directory)
    clang = shutil.which("clang")
    return Path(clang).parent if clang and all(shutil.which(t) for t in ("opt", "llvm-link")) else None


RUNTIME_C = """
static long count;                        /* the state an inlined body and the runtime share */
long pys_touch(long n) { count += n; return count; }
__attribute__((noinline)) long pys_read(void) { return count; }
"""
PROGRAM_LL = """
declare i64 @pys_touch(i64)
declare i64 @pys_read()
declare i32 @printf(ptr, ...)
@fmt = private unnamed_addr constant [12 x i8] c"%ld %ld %ld\\00"

define i32 @main() {
  %a = call i64 @pys_touch(i64 2)
  %b = call i64 @pys_touch(i64 3)
  %c = call i64 @pys_read()
  %r = call i32 (ptr, ...) @printf(ptr @fmt, i64 %a, i64 %b, i64 %c)
  ret i32 0
}
"""


@unittest.skipIf(llvm() is None, "LLVM tools not found")
class WithLLVM(unittest.TestCase):
    def run_tool(self, *args, cwd):
        result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, f"{args}: {result.stderr}")
        return result.stdout

    def test_views_verify(self):
        tools = llvm()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, text in zip(("object", "interface"), split(MODULE, BODY)[:2]):
                (root / f"{name}.ll").write_text(text)
                self.run_tool(tools / "opt", "-passes=verify", root / f"{name}.ll", "-o", root / f"{name}.bc", cwd=root)

    def program(self, root, face):
        # the program built against an interface (face) and linked with the precompiled runtime.o:
        # what it prints
        tools = llvm()
        (root / "face.ll").write_text(face)
        self.run_tool(tools / "opt", "face.ll", "-o", "face.bc", cwd=root)
        self.run_tool(tools / "llvm-link", "--only-needed", "program.ll", "face.bc", "-o", "linked.bc", cwd=root)
        self.run_tool(tools / "clang", "-O2", "-c", "-emit-llvm", "linked.bc", "-o", "optimized.bc", cwd=root)
        ir = self.run_tool(tools / "opt", "-S", "optimized.bc", "-o", "-", cwd=root)
        self.assertNotIn("call i64 @pys_touch", ir, "the small runtime function is inlined")
        self.assertIn("call i64 @pys_read", ir)
        self.run_tool(tools / "clang", "-c", "optimized.bc", "-o", "program.o", cwd=root)
        link = ["-Wl,-dead_strip"] if sys.platform == "darwin" else ["-Wl,--gc-sections"]
        self.run_tool(tools / "clang", "program.o", "runtime.o", "-o", "program", *link, cwd=root)
        return self.run_tool(root / "program", cwd=root)

    def test_one_static_for_inlined_and_runtime_code(self):
        tools = llvm()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime.c").write_text(RUNTIME_C)
            (root / "program.ll").write_text(PROGRAM_LL)
            self.run_tool(tools / "clang", "-O2", "-S", "-emit-llvm", "runtime.c", "-o", "runtime.ll", cwd=root)
            obj, face, _ = split((root / "runtime.ll").read_text(), BODY)
            self.assertIn("@count = available_externally hidden", face)
            (root / "obj.ll").write_text(obj)
            self.run_tool(tools / "clang", "-O2", "-c", "-Xclang", "-disable-llvm-passes", "-ffunction-sections",
                          "-fdata-sections", "-x", "ir", "obj.ll", "-o", "runtime.o", cwd=root)
            # the inlined increments and the runtime's own read see one count: 2, 5, 5
            self.assertEqual(self.program(root, face), "2 5 5")
            # negative control: an interface whose static were the program's own copy (as an
            # internal static left local would be) splits the count, which this test then sees
            copy = face.replace("@count = available_externally hidden", "@count = internal")
            self.assertNotEqual(copy, face)
            self.assertEqual(self.program(root, copy), "2 5 0")

if __name__ == "__main__":
    unittest.main()
