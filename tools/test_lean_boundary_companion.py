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
        cls.python = (companion.ROOT / "runtime.py").read_text(encoding="utf-8")
        cls.candidate = companion.normalize_runtime(cls.runtime)

    def changed(self, old, new):
        self.assertIn(old, self.source)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.c"
            source = self.source.replace(old, new, 1)
            source = source.replace('#include "', '#include "' + str(companion.ROOT) + '/')
            path.write_text(source)
            return companion.normalize_runtime(path)

    def changed_py(self, old, new):
        # the constructor, growth and slice copy are runtime.py's: the same control on its source
        self.assertEqual(self.python.count(old), 1, old)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.py"
            path.write_text(self.python.replace(old, new), encoding="utf-8")
            return companion.normalize_runtime(self.runtime, path)

    def test_live_allocations_layout_and_identity_offsets(self):
        self.assertEqual(self.candidate, CANDIDATE)

    @unittest.skipUnless(companion.CHECKER.is_file(), "build the Lean companion checker")
    def test_kernel_accepts_actual_companion(self):
        self.assertTrue(companion.checked(self.candidate))

    @unittest.skipUnless(companion.CHECKER.is_file(), "build the Lean companion checker")
    def test_each_atomic_allocation_loses_a_required_edge(self):
        allocation = "pys_alloc((l->cap + 1) * sizeof(I))"
        self.assertFalse(companion.checked(self.changed(allocation, allocation.replace("pys_alloc(", "pys_alloc_atomic("))))
        for allocation in ('pys_alloc(_rt.sizeof("List") + 32)', 'pys_alloc(_rt.sizeof("List") - 1)', "pys_alloc((c + 1) * 8)"):
            with self.subTest(allocation=allocation):
                changed = self.changed_py(allocation, allocation.replace("pys_alloc(", "pys_alloc_atomic("))
                self.assertFalse(companion.checked(changed))

    def test_each_atomic_allocation_changes_the_derived_edge(self):
        # (without the Lean checker: the fact that it would reject is the one derived)
        for allocation, key in (('pys_alloc(_rt.sizeof("List") + 32)', "header_scanned"), ('pys_alloc(_rt.sizeof("List") - 1)', "header_scanned"),
                                ("pys_alloc((c + 1) * 8)", "growth")):
            with self.subTest(allocation=allocation):
                changed = self.changed_py(allocation, allocation.replace("pys_alloc(", "pys_alloc_atomic("))
                expected = copy.deepcopy(CANDIDATE)
                if key == "growth":
                    expected["growth"]["array_scanned"] = False
                else:
                    expected[key] = False
                self.assertEqual(changed, expected)

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
        for old, new in (('l = pys_alloc(_rt.sizeof("List") - 1)', 'l = pys_alloc(_rt.sizeof("List") - 9)'),
                         ('l = pys_alloc(_rt.sizeof("List") + 32)', 'l = pys_alloc(_rt.sizeof("List") + 24)'),
                         ('        _rt.setp(l, "List.a", list_inline(l))\n        return l', '        _rt.setp(l, "List.ids", list_inline(l))\n        return l'),
                         ('    _rt.setp(l, "List.a", item_array(c, atomic))', '    _rt.setp(l, "List.ids", item_array(c, atomic))')):
            with self.subTest(new=new), self.assertRaisesRegex(ValueError, "unsupported companion function shape: pys_list_make"):
                self.changed_py(old, new)

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
        copied = '        _rt.cpy(ids, _rt.getp(l, "List.ids"), (_rt.get(l, "List.len") + 1) * 8)\n'
        attached = '        _rt.setp(l, "List.ids", ids)\n'
        for replacement in (
                '        _rt.cpy(ids, _rt.getp(l, "List.ids"), _rt.get(l, "List.len") * 8)\n' + attached,
                '        _rt.cpy(ids, _rt.at(_rt.getp(l, "List.ids"), 1), (_rt.get(l, "List.len") + 1) * 8)\n' + attached,
                '        _rt.cpy(_rt.at(ids, 1), _rt.getp(l, "List.ids"), (_rt.get(l, "List.len") + 1) * 8)\n' + attached,
                '        _rt.cpy(ids, _rt.getp(l, "List.a"), (_rt.get(l, "List.len") + 1) * 8)\n' + attached,
                '        _rt.move(ids, _rt.getp(l, "List.ids"), (_rt.get(l, "List.len") + 1) * 8)\n' + attached,
                copied,
                copied + '        _rt.setp(l, "List.a", ids)\n',
                copied + attached + '        _rt.setp(l, "List.ids", _rt.nil())\n'):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "unsupported companion function shape: pys_list_reserve"):
                self.changed_py(copied + attached, replacement)
        with self.assertRaises(ValueError):
            self.changed_py("ids = pys_alloc((c + 1) * 8)", "ids = pys_alloc(c * 8)")

    def test_slice_copy_extent_offsets_and_result_are_checked(self):
        copied = '        _rt.cpy(_rt.at(_rt.getp(r, "List.ids"), 1), _rt.at(ids, lo + 1), (hi - lo) * 8)\n'
        for replacement in (
                '        _rt.cpy(_rt.at(_rt.getp(r, "List.ids"), 1), _rt.at(ids, lo), (hi - lo) * 8)\n',
                '        _rt.cpy(_rt.getp(r, "List.ids"), _rt.at(ids, lo + 1), (hi - lo) * 8)\n',
                '        _rt.cpy(_rt.at(_rt.getp(r, "List.ids"), 1), _rt.at(ids, lo + 1), (hi - lo - 1) * 8)\n',
                '        _rt.cpy(_rt.at(_rt.getp(r, "List.ids"), 1), _rt.at(_rt.getp(l, "List.a"), lo + 1), (hi - lo) * 8)\n',
                copied + '        _rt.setp(r, "List.ids", ids)\n'):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "unsupported companion function shape: pys_list_slice"):
                self.changed_py(copied, replacement)
        with self.assertRaisesRegex(ValueError, "unsupported companion function shape: pys_list_copy"):
            self.changed_py("return pys_list_slice(l, -9223372036854775807 - 1, -9223372036854775807 - 1)",
                            "return pys_list_slice(l, 1, -9223372036854775807 - 1)")

    def test_runtime_py_cannot_redefine_what_the_contract_calls(self):
        # the contract's trees name the allocator: runtime.py may only declare it
        declared = "def pys_alloc(n: int) -> _rt.Ptr: ...\n"
        for replacement in ("def pys_alloc(n: int) -> _rt.Ptr:\n    return pys_alloc_atomic(n)\n",
                            declared + "def pys_alloc(n: int) -> _rt.Ptr: ...\n",
                            ""):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "allocator|declare"):
                self.changed_py(declared, replacement)
        with self.assertRaisesRegex(ValueError, "binds a module name"):
            self.changed_py(declared, declared + "pys_alloc_atomic = pys_alloc\n")
        with self.assertRaisesRegex(ValueError, "duplicate companion function"):
            self.changed_py("def pys_list_copy(l: _rt.Ptr) -> _rt.Ptr:\n", "def pys_list_copy(l: _rt.Ptr) -> _rt.Ptr:\n    return l\n\n\ndef pys_list_copy(l: _rt.Ptr) -> _rt.Ptr:\n")

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
        start = "static __attribute__((noinline)) void list_identity_slow(List *l, I kind) {"
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
