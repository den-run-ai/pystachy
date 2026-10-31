"""Native C result ABI controls for the compiler's two-word promoting ints."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from check_runtime import BIG_ABI_PROBE, big_layout_errors, c_declaration, functions


CLANG = shutil.which(str(Path(os.environ["PYSTACHY_LLVM"]) / "clang") if os.environ.get("PYSTACHY_LLVM") else "clang")
DECL = "declare {i64, ptr} @check_big_abi(i64, ptr)"


class RuntimeSignatures(unittest.TestCase):
    def test_complete_aggregate_result_is_parsed(self):
        for result in ("[2 x i64]", "[3 x i64]", "[2 x i32]", "{ i64, ptr }"):
            with self.subTest(result=result):
                ir = f"define dso_local {result} @f(i64 noundef %0, ptr noundef %1) #0 {{\n}}"
                have = functions(ir)["f"]
                self.assertEqual(have[0], result.replace("{ ", "{").replace(" }", "}"))
                self.assertEqual(have[1], ["i64", "ptr"])

    def test_only_the_probed_big_result_changes(self):
        self.assertEqual(c_declaration(DECL, "{i64, ptr}"), DECL)
        expected = "declare [2 x i64] @check_big_abi(i64, ptr)"
        self.assertEqual(c_declaration(DECL, "[2 x i64]"), expected)
        for wrong in (expected.replace("[2 x i64]", "[3 x i64]"),
                      expected.replace("[2 x i64]", "[2 x i32]"),
                      expected.replace("(i64, ptr)", "(i32, ptr)"),
                      expected.replace("(i64, ptr)", "(ptr, i64)")):
            with self.subTest(wrong=wrong):
                self.assertNotEqual(c_declaration(DECL, "[2 x i64]"), wrong)
        other = "declare {ptr, i64} @f(i64, ptr)"
        self.assertEqual(c_declaration(other, "[2 x i64]"), other)

    def test_unrecognized_probe_result_fails_closed(self):
        for result in ("", "i64]", "[3 x i64]", "[2 x i32]", "ptr"):
            with self.subTest(result=result), self.assertRaisesRegex(ValueError, "unsupported C ABI"):
                c_declaration(DECL, result)

    def test_big_payload_width_and_order_are_not_erased_by_the_abi(self):
        self.assertEqual(big_layout_errors("%struct.Big = type { i64, ptr }"), [])
        for ir in ("", "%struct.Big = type { i32, ptr }", "%struct.Big = type { ptr, i64 }",
                   "%struct.Big = type { i64, i64 }"):
            with self.subTest(ir=ir):
                self.assertTrue(big_layout_errors(ir))

    @unittest.skipUnless(CLANG, "clang is required for native result ABI controls")
    def test_independent_c_probe_for_each_supported_abi(self):
        for target, expected in (("x86_64-linux-gnu", "{i64, ptr}"),
                                 ("aarch64-linux-gnu", "[2 x i64]"),
                                 ("arm64-apple-darwin", "[2 x i64]")):
            with self.subTest(target=target):
                result = subprocess.run([CLANG, "-target", target, "-S", "-emit-llvm", "-O0",
                                         "-x", "c", "-", "-o", "-"], input=BIG_ABI_PROBE,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                have = functions(result.stdout)["check_big_abi"]
                self.assertEqual(have[0], expected)
                self.assertEqual(have[1], ["i64", "ptr"])
                self.assertEqual(c_declaration(DECL, have[0]),
                                 f"declare {expected} @check_big_abi(i64, ptr)")

    @unittest.skipUnless(CLANG, "clang is required for native result ABI controls")
    def test_same_arm_result_abi_cannot_hide_a_wrong_c_payload(self):
        original = BIG_ABI_PROBE.replace("CheckBig", "Big")
        for source in (original.replace("__INT64_TYPE__ lo;", "__INT32_TYPE__ lo;"),
                       original.replace("__INT64_TYPE__ lo; void *hi;", "void *hi; __INT64_TYPE__ lo;")):
            with self.subTest(source=source):
                result = subprocess.run([CLANG, "-target", "aarch64-linux-gnu", "-S", "-emit-llvm",
                                         "-O0", "-x", "c", "-", "-o", "-"], input=source,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(functions(result.stdout)["check_big_abi"][0], "[2 x i64]")
                self.assertTrue(big_layout_errors(result.stdout))


if __name__ == "__main__":
    unittest.main()
