"""wasm/wasm32_ir.py: wasm32's constants keep the layout that native code reads (wasm/README.md)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wasm import wasm32_ir as W


class Wasm32Ir(unittest.TestCase):
    def test_array_of_addresses_becomes_packed_struct(self):
        line = "@tc.0 = private constant [2 x i64] [i64 ptrtoint (ptr @s.1 to i64), i64 5], align 8"
        self.assertEqual(W.line_of(line), "@tc.0 = private constant <{<{ptr, i32}>, i64}> "
                                          "<{<{ptr, i32}> <{ptr @s.1, i32 0}>, i64 5}>, align 8")

    def test_struct_member_keeps_its_offset(self):
        # a dynamic box {DynType *, I}: the value stays at offset 8 behind a 4-byte pointer
        line = "@dbs.0 = internal constant {ptr, i64} {ptr @pys_dyntype_str, i64 ptrtoint (ptr @s.0 to i64)}, align 8"
        self.assertEqual(W.line_of(line), "@dbs.0 = internal constant <{ptr, [4 x i8], <{ptr, i32}>}> <{ptr @pys_dyntype_str, "
                                          "[4 x i8] zeroinitializer, <{ptr, i32}> <{ptr @s.0, i32 0}>}>, align 8")

    def test_trailing_padding_keeps_the_size(self):
        self.assertEqual(W.struct_layout(["i64", "ptr"]), ([0, 8], 16, 8))
        line = "@x = internal constant {i64, ptr, i64} {i64 ptrtoint (ptr @a to i64), ptr @b, i64 1}, align 8"
        t = "<{<{ptr, i32}>, ptr, [4 x i8], i64}>"
        self.assertEqual(W.line_of(line), f"@x = internal constant {t} <{{<{{ptr, i32}}> <{{ptr @a, i32 0}}>, ptr @b, "
                                          "[4 x i8] zeroinitializer, i64 1}>, align 8")
        self.assertEqual(W.layout(t)[0], W.layout("{i64, ptr, i64}")[0])

    def test_other_lines_unchanged(self):
        for line in ["@g.x = internal global ptr zeroinitializer",
                     "@s.0 = private unnamed_addr global {i64, i64, i64, [2 x i8]} {i64 1, i64 0, i64 2, [2 x i8] c\" \\00\"}, align 8",
                     "  %p = call ptr @pys_new(i64 ptrtoint (ptr getelementptr (%C.Point, ptr null, i32 1) to i64))"]:
            self.assertEqual(W.line_of(line), line)

    def test_main_and_sized_calls(self):
        self.assertEqual(W.line_of("define i32 @main(i32 %argc, ptr %argv) {"), "define i32 @__main_argc_argv(i32 %argc, ptr %argv) {")
        self.assertEqual(W.line_of("declare i32 @memcmp(ptr, ptr, i64)"), "declare i32 @pys_wasi_memcmp(ptr, ptr, i64)")
        self.assertEqual(W.line_of("  %r = call double @llvm.fma.f64(double %a, double %b, double 0.0)"),
                         "  %r = call double @pys_wasi_fma(double %a, double %b, double 0.0)")

    def test_retarget_only_exception_instructions(self):
        literal = '@s = private constant [49 x i8] c"  invoke void @f() to label %ok unwind label %pad"'
        src = "\n".join([literal, "define i32 @main(i32 %argc, ptr %argv) {", "  call void @pys_eh_on()",
                         "  ret i32 0", "}", "define void @f() personality ptr @pys_personality {",
                         "  invoke void @g() to label %ok unwind label %land, !dbg !5", "land:",
                         "  %x = landingpad { ptr, i32 } catch ptr null, !dbg !5",
                         "  %e = extractvalue { ptr, i32 } %x, 0, !dbg !5", "  br label %ok",
                         "ok:", "  ret void", "}"])
        result = W.adapt_module(src)
        self.assertIn(literal, result)
        self.assertIn("unwind label %pys.wasi.dispatch.land, !dbg !5", result)
        self.assertIn("catchret from %pys.wasi.pad.land.token to label %land\nland:\n  br label %ok", result)
        self.assertIn("%e = call ptr @llvm.wasm.get.exception(token %pys.wasi.pad.land.token), !dbg !5", result)
        with self.assertRaisesRegex(ValueError, "unsupported WASI landing pad"):
            W.adapt_module(src.replace("catch ptr null", "cleanup"))
        self.assertEqual(W.adapt_module(literal), literal)

    def test_wasi_symbols_preserve_literal_bytes_and_comments(self):
        literal = r'@s.0 = private constant [10 x i8] c"\22@memcmp(\00"'
        self.assertEqual(W.line_of(literal), literal)
        self.assertEqual(W.line_of("  %p = call ptr @memchr(ptr %s, i32 1, i64 2) ; @memmem("),
                         "  %p = call ptr @pys_wasi_memchr(ptr %s, i32 1, i64 2) ; @memmem(")


if __name__ == "__main__":
    unittest.main()
