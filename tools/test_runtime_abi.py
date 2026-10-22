"""Mutation controls for Str's named ABI, beyond its three identical LLVM words."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pystachy_compiler.ir import Data
from src.pystachy_compiler.lower_module import lower_data
from src.pystachy_compiler.specs import STR_HEADER_SIZE
from tools.strabi import STR_PROBE, llvm_bytes, str_literal_errors, str_offset_errors, str_offsets


ROOT = Path(__file__).resolve().parents[1]
CLANG = shutil.which(str(Path(os.environ["PYSTACHY_LLVM"]) / "clang") if os.environ.get("PYSTACHY_LLVM") else "clang")
OFFSETS = {"len": 0, "dict_hash": 8, "chars1": 16, "s": 24, "size": 24}


def literal(text):
    data = Data("string", "@s.0")
    data.text = text
    return lower_data(data)


class StringABI(unittest.TestCase):
    def test_compiler_header_matches_c_offsets(self):
        self.assertEqual(str_offset_errors(OFFSETS, STR_HEADER_SIZE), [])
        self.assertTrue(str_offset_errors(OFFSETS, STR_HEADER_SIZE + 8))

    def test_swapped_same_typed_fields_fail(self):
        swapped = dict(OFFSETS, dict_hash=16, chars1=8)
        self.assertEqual(len(str_offset_errors(swapped, STR_HEADER_SIZE)), 2)

    def test_missing_offset_probe_fails_closed(self):
        self.assertEqual(len(str_offset_errors({}, STR_HEADER_SIZE)), 5)

    def test_emitted_literal_semantics(self):
        for text in ("", "ascii", 'a\x00b"\\', "\xc3\xa9", "\xf0\x9f\x98\x80"):
            with self.subTest(text=text):
                self.assertEqual(str_literal_errors(literal(text)), [])

    def test_same_typed_literal_word_swaps_fail(self):
        source = literal("abc")
        for changed in ("i64 3, i64 4, i64 0", "i64 0, i64 3, i64 4", "i64 4, i64 0, i64 3"):
            with self.subTest(changed=changed):
                self.assertTrue(str_literal_errors(source.replace("i64 3, i64 0, i64 4", changed)))

    def test_literal_length_nul_and_escape_controls(self):
        source = literal("abc")
        for changed in (source.replace("[4 x i8]", "[5 x i8]"), source.replace("\\00", "x"),
                        source.replace("\\00", "\\0X"), source.replace("i64 3,", "i32 3,"), ""):
            with self.subTest(changed=changed):
                self.assertTrue(str_literal_errors(changed))
        with self.assertRaises(ValueError):
            llvm_bytes("\\0")

    @unittest.skipUnless(CLANG, "clang is required for the C ABI mutation controls")
    def test_each_c_copy_asserts_named_field_order(self):
        for filename in ("runtime.c", "pyext.c", "pyembed.c"):
            source = (ROOT / filename).read_text()
            declaration = re.search(r"typedef struct \{ I len;[^\n]+\} Str;[^\n]*\n", source).group()
            assertion = re.search(r"_Static_assert\(offsetof\(Str, len\).*?;", source, re.S).group()
            probe = "#include <stdint.h>\n#include <stddef.h>\ntypedef int64_t I;\n" + declaration + assertion
            with self.subTest(filename=filename):
                good = subprocess.run([CLANG, "-x", "c", "-fsyntax-only", "-"], input=probe,
                                      capture_output=True, text=True)
                self.assertEqual(good.returncode, 0, good.stderr)
                swapped = probe.replace("uint64_t dict_hash; I chars1;", "I chars1; uint64_t dict_hash;")
                bad = subprocess.run([CLANG, "-x", "c", "-fsyntax-only", "-"], input=swapped,
                                     capture_output=True, text=True)
                self.assertNotEqual(bad.returncode, 0)
                self.assertIn("Str ABI", bad.stderr)
                layout = subprocess.run([CLANG, "-x", "c", "-S", "-emit-llvm", "-o", "-", "-"],
                                        input=probe + STR_PROBE, capture_output=True, text=True)
                self.assertEqual(layout.returncode, 0, layout.stderr)
                self.assertEqual(str_offsets(layout.stdout), OFFSETS)


if __name__ == "__main__":
    unittest.main()
