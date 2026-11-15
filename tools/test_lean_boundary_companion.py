"""Source-derived list companion edges and fail-closed mutation controls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import check_lean_companion as companion

CANDIDATE = {"schema_version": 2, "header_words": 4, "header_scanned": True,
             "store_word": 3, "read_word": 3, "array_scanned": True, "prefix_words": 1,
             "store_offset": 1, "read_offset": 1,
             "growth": {"array_scanned": True, "allocation_prefix": 1, "source_offset": 0,
                        "target_offset": 0, "copy_extra": 1},
             "slice": {"array_scanned": True, "allocation_prefix": 1, "source_offset": 1,
                       "target_offset": 1, "copy_extra": 0}}


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
        self.assertEqual(self.candidate, CANDIDATE)

    @unittest.skipUnless(companion.CHECKER.is_file(), "build the Lean companion checker")
    def test_kernel_accepts_actual_companion(self):
        self.assertTrue(companion.checked(self.candidate))

    @unittest.skipUnless(companion.CHECKER.is_file(), "build the Lean companion checker")
    def test_each_atomic_allocation_loses_a_required_edge(self):
        for allocation in ("pys_alloc(sizeof(List) + INLINE_CAP * sizeof(I))",
                           "pys_alloc(sizeof(List) - 1)",
                           "pys_alloc((l->cap + 1) * sizeof(I))",
                           "pys_alloc((c + 1) * sizeof(I))"):
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

    def test_growth_copy_extent_source_and_attachment_are_checked(self):
        copy = "memcpy(ids, l->ids, (l->len + 1) * sizeof(I)); l->ids = ids;"
        for replacement in (
                "memcpy(ids, l->ids, l->len * sizeof(I)); l->ids = ids;",
                "memcpy(ids, l->ids + 1, (l->len + 1) * sizeof(I)); l->ids = ids;",
                "memcpy(ids + 1, l->ids, (l->len + 1) * sizeof(I)); l->ids = ids;",
                "memcpy(ids, l->a, (l->len + 1) * sizeof(I)); l->ids = ids;",
                "memcpy(ids, l->ids, (l->len + 1) * sizeof(I));",
                copy + " l->ids = NULL;"):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                self.changed(copy, replacement)
        with self.assertRaises(ValueError):
            self.changed("I *ids = pys_alloc((c + 1) * sizeof(I));",
                         "I *ids = pys_alloc(c * sizeof(I));")

    def test_slice_copy_extent_offsets_and_result_are_checked(self):
        copy = "memcpy(r->ids + 1, l->ids + lo + 1, (hi - lo) * 8);"
        for replacement in (
                "memcpy(r->ids + 1, l->ids + lo, (hi - lo) * 8);",
                "memcpy(r->ids, l->ids + lo + 1, (hi - lo) * 8);",
                "memcpy(r->ids + 1, l->ids + lo + 1, (hi - lo - 1) * 8);",
                "memcpy(r->ids + 1, l->a + lo + 1, (hi - lo) * 8);",
                copy + " r->ids = l->ids;"):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                self.changed(copy, replacement)
        with self.assertRaises(ValueError):
            self.changed("return pys_list_slice(l, NONE, NONE);", "return pys_list_slice(l, 1, NONE);")

    def test_macros_cannot_rewrite_the_independent_copy_contract(self):
        start = "static void reserve(List *l, I n) {"
        with self.assertRaisesRegex(ValueError, "unsupported companion function shape: reserve"):
            self.changed(start, "#define memcpy(dst, src, size) memset(dst, 0, size)\n" + start)

    def test_clean_companion_fast_path_cannot_mutate_or_reclassify(self):
        guard = "if (!l->ids || (l->ids[0] & 4) || ((kind & 3) == 1 && big_list(l)))"
        with self.assertRaises(ValueError):
            self.changed(guard, "l->ids[1] = 0; " + guard)
        with self.assertRaises(ValueError):
            self.changed("return l->ids && (l->ids[0] & 3) == BIGIDS && opt_in();", "return 1;")

    def test_growth_length_and_capacity_words_cannot_narrow(self):
        declaration = "typedef struct { I len, cap; I *a, *ids; } List;"
        for replacement in ("typedef struct { int32_t len; I cap; I *a, *ids; } List;",
                            "typedef struct { I len; int32_t cap; I *a, *ids; } List;"):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "pointer/word ABI"):
                self.changed(declaration, replacement)

    def test_header_fields_cannot_overlap_even_with_a_matching_static_assert(self):
        declaration = "typedef struct { I len, cap; I *a, *ids; } List;"
        start = self.source.index(declaration)
        end = self.source.index('"List ABI: raw prefix and identity companion");', start)
        end += len('"List ABI: raw prefix and identity companion");')
        header = self.source[start:end]
        # The old adapter accepted this internally consistent C layout and
        # certified the ids word, although every raw-array pointer store changed
        # the companion pointer too. The source's assertion is not an oracle.
        overlapping = header.replace(declaration,
            "typedef struct { I len, cap; union { I *a; I *ids; }; } List;")
        overlapping = overlapping.replace("offsetof(List, ids) == 24 && sizeof(List) == 32",
                                          "offsetof(List, ids) == 16 && sizeof(List) == 24")
        with self.assertRaisesRegex(ValueError, "overlapping or invalid companion header fields"):
            self.changed(header, overlapping)

    def test_field_macros_cannot_redirect_both_code_and_layout_extraction(self):
        start = "static List *list_new(I cap, int atomic) {"
        with self.assertRaisesRegex(ValueError, "unsupported companion function shape"):
            self.changed(start, "#define ids a\n" + start)

    def test_raw_slot_stride_offset_and_width_are_independent_layout_obligations(self):
        declaration = "typedef struct { I v; } Slot;"
        for replacement in ("typedef struct { I padding, v; } Slot;",
                            "typedef struct { I v, padding; } Slot;",
                            "typedef struct { int32_t v, padding; } Slot;"):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "raw list slot"):
                self.changed(declaration, replacement)


@unittest.skipUnless(companion.CHECKER.is_file(), "build the Lean companion checker")
class NativeCompanionTests(unittest.TestCase):
    candidate = CANDIDATE

    def test_both_edges_and_matching_in_bounds_offsets_are_required(self):
        for key, value in (("header_scanned", False), ("array_scanned", False),
                           ("header_words", 3), ("store_word", 4), ("read_word", 0),
                           ("prefix_words", 0), ("prefix_words", 2),
                           ("store_offset", 0), ("read_offset", 0)):
            with self.subTest(key=key, value=value):
                changed = dict(self.candidate, **{key: value})
                self.assertFalse(companion.checked(changed))

    def test_copy_contracts_require_full_extents_offsets_and_scanning(self):
        for operation in ("growth", "slice"):
            for key in ("array_scanned", "allocation_prefix", "source_offset", "target_offset", "copy_extra"):
                changed = copy.deepcopy(self.candidate)
                value = changed[operation][key]
                changed[operation][key] = False if key == "array_scanned" else value + 1
                with self.subTest(operation=operation, key=key):
                    self.assertFalse(companion.checked(changed))

    def test_copy_contracts_cannot_be_omitted_downgraded_or_extended(self):
        candidates = []
        for operation in ("growth", "slice"):
            for mode in ("missing", "extra", "wrong_type", "oversized"):
                changed = copy.deepcopy(self.candidate)
                if mode == "missing":
                    del changed[operation]["copy_extra"]
                elif mode == "extra":
                    changed[operation]["unchecked"] = True
                else:
                    changed[operation]["copy_extra"] = True if mode == "wrong_type" else 65
                candidates.append(changed)
        downgraded = copy.deepcopy(self.candidate)
        downgraded["schema_version"] = 1
        del downgraded["growth"], downgraded["slice"]
        candidates.append(downgraded)
        for candidate in candidates:
            result = subprocess.run([str(companion.CHECKER)], input=json.dumps(candidate), text=True,
                                    capture_output=True, timeout=10)
            with self.subTest(candidate=candidate):
                self.assertEqual(result.returncode, 2)
                self.assertFalse(json.loads(result.stdout)["accepted"])

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
