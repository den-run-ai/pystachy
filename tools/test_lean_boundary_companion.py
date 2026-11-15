"""Source-derived list companion edges and fail-closed mutation controls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import check_lean_companion as companion


if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not companion.CHECKER.is_file():
    raise RuntimeError("Lean companion checker is required; build tools/lean_boundary first")
if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not companion.alias.clang_path():
    raise RuntimeError("clang is required for live companion correspondence")


@unittest.skipUnless(companion.alias.clang_path(), "clang is required for companion correspondence")
class RuntimeCompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = companion.ROOT / "runtime.c"
        cls.source = cls.runtime.read_text()
        cls.candidate = companion.normalize_runtime(cls.runtime)

    def changed(self, old, new):
        self.assertIn(old, self.source)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.c"
            source = self.source.replace(old, new, 1)
            source = source.replace('#include "', '#include "' + str(companion.ROOT) + '/')
            path.write_text(source)
            return companion.normalize_runtime(path)

    def test_live_allocations_layout_and_identity_offsets(self):
        self.assertEqual(self.candidate, {"schema_version": 1, "header_words": 4,
                         "header_scanned": True, "store_word": 3, "read_word": 3,
                         "array_scanned": True, "prefix_words": 1,
                         "store_offset": 1, "read_offset": 1})

    @unittest.skipUnless(companion.CHECKER.is_file(), "build the Lean companion checker")
    def test_kernel_accepts_actual_companion(self):
        self.assertTrue(companion.checked(self.candidate))

    @unittest.skipUnless(companion.CHECKER.is_file(), "build the Lean companion checker")
    def test_each_atomic_allocation_loses_a_required_edge(self):
        for allocation in ("pys_alloc(sizeof(List) + INLINE_CAP * sizeof(I))",
                           "pys_alloc(sizeof(List) - 1)",
                           "pys_alloc((l->cap + 1) * sizeof(I))"):
            with self.subTest(allocation=allocation):
                changed = self.changed(allocation, allocation.replace("pys_alloc(", "pys_alloc_atomic("))
                self.assertFalse(companion.checked(changed))

    def test_missing_wrong_and_overwritten_attachment_fail_closed(self):
        mask = 11 if "ids[0] = kind & 11; l->ids = ids;" in self.source else 3
        prefix = f"ids[0] = kind & {mask};"
        for replacement in (prefix, prefix + " l->a = ids;", prefix + " l->ids = ids + 1;",
                            prefix + " l->ids = ids; l->ids = NULL;"):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                self.changed(prefix + " l->ids = ids;", replacement)

    def test_changed_extent_and_identity_stores_fail_closed(self):
        for old, new in (
                ("I *ids = pys_alloc((l->cap + 1) * sizeof(I));", "I *ids = pys_alloc(l->cap * sizeof(I));"),
                ("List *l = pys_alloc(sizeof(List) - 1);", "List *l = pys_alloc(sizeof(List) - 9);"),
                ("pys_list_identity(l, kind); l->ids[i + 1] = (I)id; AT(l, i) = v;",
                 "pys_list_identity(l, kind); l->ids[i] = (I)id; AT(l, i) = v;"),
                ("pys_list_identity(l, kind); l->ids[i + 1] = (I)id; AT(l, i) = v;",
                 "pys_list_identity(l, kind); l->ids[i + 1] = v; AT(l, i) = v;"),
                ("pys_list_identity(l, kind); l->ids[i + 1] = (I)id; AT(l, i) = v;",
                 "pys_list_identity(l, kind); l->ids[i + 1] = (int32_t)(I)id; AT(l, i) = v;"),
                ("pys_list_identity(l, kind); l->ids[i + 1] = (I)id; AT(l, i) = v;",
                 "pys_list_identity(l, kind); l->ids[i + 1] = (I)id; l->ids[i + 1] = 0; AT(l, i) = v;"),
                ("return (Dyn *)l->ids[i + 1];", "return (Dyn *)l->ids[i];"),
                ("return (Dyn *)l->ids[i + 1];", "return (Dyn *)l->a[i + 1];")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.changed(old, new)

    def test_macro_cannot_redirect_raw_store_into_the_identity_array(self):
        # Reference contract deliberately spells out Slot/a instead of using AT.
        with self.assertRaisesRegex(ValueError, "unsupported companion function shape"):
            self.changed("#define AT(l, i) (((Slot *)(l)->a)[i].v)",
                         "#define AT(l, i) (((Slot *)(l)->ids)[i + 1].v)")

    def test_scoped_macro_narrowing_is_checked_in_the_real_translation_unit(self):
        declaration = "typedef struct { I len, cap; I *a, *ids; } List;"
        with self.assertRaises(ValueError):
            self.changed(declaration, "#define I int32_t\n" + declaration + "\n#undef I")


@unittest.skipUnless(companion.CHECKER.is_file(), "build the Lean companion checker")
class NativeCompanionTests(unittest.TestCase):
    candidate = {"schema_version": 1, "header_words": 4, "header_scanned": True,
                 "store_word": 3, "read_word": 3, "array_scanned": True,
                 "prefix_words": 1, "store_offset": 1, "read_offset": 1}

    def test_both_edges_and_matching_in_bounds_offsets_are_required(self):
        for key, value in (("header_scanned", False), ("array_scanned", False),
                           ("header_words", 3), ("store_word", 4), ("read_word", 0),
                           ("prefix_words", 0), ("prefix_words", 2),
                           ("store_offset", 0), ("read_offset", 0)):
            with self.subTest(key=key, value=value):
                changed = dict(self.candidate, **{key: value})
                self.assertFalse(companion.checked(changed))

    def test_schema_missing_extra_and_oversized_fields_fail_closed(self):
        for mode in ("schema", "missing", "extra", "oversized", "negative"):
            candidate = copy.deepcopy(self.candidate)
            if mode == "schema":
                candidate["schema_version"] = 0
            elif mode == "missing":
                del candidate["array_scanned"]
            elif mode == "extra":
                candidate["trusted"] = True
            else:
                candidate["read_offset"] = 65 if mode == "oversized" else -1
            result = subprocess.run([str(companion.CHECKER)], input=json.dumps(candidate), text=True,
                                    capture_output=True, timeout=10)
            with self.subTest(mode=mode):
                self.assertEqual(result.returncode, 2)
                self.assertFalse(json.loads(result.stdout)["accepted"])


if __name__ == "__main__":
    unittest.main()
