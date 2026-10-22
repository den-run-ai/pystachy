"""Adversarial controls for the static pointer inventory and actual root scans."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from runtime_roots import check_roots, compile_inventory, pointer_statics


ROOT = Path(__file__).resolve().parents[1]
CLANG = str(Path(os.environ["PYSTACHY_LLVM"]) / "clang") if os.environ.get("PYSTACHY_LLVM") else "clang"
PRELUDE = "typedef unsigned long W; typedef struct { long len; } Str; void scan(const W *, const W *);\n"
VALID = PRELUDE + """
/* GC_ROOT(value): strong runtime reference. */
static Str *value;
static void mark_roots(void) { scan((const W *)&value, (const W *)(&value + 1)); }
"""


@unittest.skipUnless(shutil.which(CLANG), "clang is required for the runtime root contract")
class RuntimeRootTests(unittest.TestCase):
    def problems(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roots.c"
            path.write_text(source)
            return check_roots(source, compile_inventory(path))

    def test_current_runtime_inventory(self):
        source = ROOT / "runtime.c"
        ir = compile_inventory(source)
        self.assertEqual(check_roots(source.read_text(), ir), [])
        self.assertTrue({"warnopts", "xr", "text_hints", "codec.alias"} <= pointer_statics(ir))

    def test_unused_new_pointer_cannot_disappear(self):
        self.assertEqual(self.problems(VALID), [])
        bad = self.problems(VALID + "static Str *x;\n")
        self.assertIn("GC roots: unclassified static pointer storage x", bad)

    def test_alias_array_struct_union_and_thread_local_inventory(self):
        source = PRELUDE + """
typedef Str *Ptr;
typedef struct { Ptr value; } Box;
static Ptr alias;
static Ptr array[3];
static Box box;
static struct { Box nested; } aggregate;
static union { long words[4]; Ptr pointer; } variant;
static _Thread_local Ptr thread;
"""
        bad = self.problems(source)
        self.assertEqual(set(bad), {f"GC roots: unclassified static pointer storage {name}"
                                    for name in ["alias", "array", "box", "aggregate", "variant", "thread"]})

    def test_function_local_static_requires_classification(self):
        source = PRELUDE + "static void f(void) { static Str *p; }\n"
        self.assertEqual(self.problems(source), ["GC roots: unclassified static pointer storage f.p"])
        self.assertEqual(self.problems("/* GC_NO_ROOT(f.p): test-only dormant pointer. */\n" + source), [])

    def test_automatic_initializer_template_is_not_static_storage(self):
        source = 'void sink(const char **); void f(void) { const char *items[2] = {"a", "b"}; sink(items); }'
        self.assertEqual(self.problems(source), [])
        self.assertIn("GC roots: unclassified static pointer storage f.items",
                      self.problems(source.replace("const char *items", "static const char *items")))

    def test_removed_commented_and_dead_scan_are_rejected(self):
        scan = "scan((const W *)&value, (const W *)(&value + 1));"
        for replacement in ["", "/* " + scan + " */", "if (0) { " + scan + " }"]:
            with self.subTest(replacement=replacement):
                self.assertIn("GC roots: value is not scanned by mark_roots with ROOT storage semantics",
                              self.problems(VALID.replace(scan, replacement)))

    def test_zero_length_scan_is_rejected(self):
        self.assertIn("GC roots: value is not scanned by mark_roots with ROOT storage semantics",
                      self.problems(VALID.replace("(&value + 1)", "&value")))
        source = PRELUDE + """
/* GC_ROOT_RANGE(value): malloc-backed array to scan. */
static Str **value;
static void mark_roots(void) { scan((const W *)value, (const W *)value); }
"""
        self.assertIn("GC roots: value is not scanned by mark_roots with ROOT_RANGE storage semantics", self.problems(source))

    def test_only_one_scan_bound_is_insufficient(self):
        self.assertIn("GC roots: value is not scanned by mark_roots with ROOT storage semantics",
                      self.problems(VALID.replace("(const W *)(&value + 1)", "(const W *)0")))

    def test_dynamic_root_range_uses_pointer_base(self):
        source = PRELUDE + """
/* GC_ROOT_RANGE(value): active range of a malloc-backed root array. */
static Str **value;
static long count;
static void mark_roots(void) { if (count) scan((const W *)value, (const W *)(value + count)); }
"""
        self.assertEqual(self.problems(source), [])

    def test_managed_object_contents_are_not_a_holding_root(self):
        source = VALID.replace("(const W *)&value", "(const W *)value").replace("(&value + 1)", "(value + 1)")
        self.assertIn("GC roots: value is not scanned by mark_roots with ROOT storage semantics", self.problems(source))

    def test_malloc_root_table_requires_its_contents(self):
        source = VALID.replace("GC_ROOT(value)", "GC_ROOT_RANGE(value)")
        self.assertIn("GC roots: value is not scanned by mark_roots with ROOT_RANGE storage semantics", self.problems(source))

    def test_unknown_duplicate_and_empty_annotations_fail(self):
        for annotation, expected in [
            ("/* GC_NO_ROOT(missing): no declaration. */", "annotation names no static pointer storage: missing"),
            ("/* GC_NO_ROOT(value): duplicate. */", "duplicate annotation for value"),
            ("/* GC_NO_ROOT(missing): */", "malformed annotation for 'missing'"),
        ]:
            with self.subTest(annotation=annotation):
                self.assertTrue(any(expected in p for p in self.problems(VALID + annotation)))


if __name__ == "__main__":
    unittest.main()
