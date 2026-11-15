"""Live C/LLVM reference transfers and independent alias/root mutation controls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import check_lean_alias as alias


if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not alias.CHECKER.is_file():
    raise RuntimeError("Lean reference alias checker is required; build tools/lean_boundary first")
if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not alias.clang_path():
    raise RuntimeError("clang is required for the live reference alias correspondence")


@unittest.skipUnless(alias.clang_path(), "clang is required for runtime transfer correspondence")
class RuntimeAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = alias.ROOT / "runtime.c"
        cls.source = cls.runtime.read_text()
        cls.candidate = alias.normalize_runtime(cls.runtime)

    def changed(self, old, new):
        self.assertIn(old, self.source)
        # Quoted includes resolve against the real runtime's directory, including
        # its bundled mpz/ryu files, without mutating the checkout under test.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.c"
            source = self.source.replace(old, new, 1)
            source = source.replace('#include "', '#include "' + str(alias.ROOT) + '/')
            path.write_text(source)
            return alias.normalize_runtime(path)

    def test_live_reference_transfer(self):
        self.assertEqual(self.candidate, {"schema_version": 1, "words": 2, "scanned": True,
                                         "stores": [{"word": 0, "source": "tag"},
                                                    {"word": 1, "source": "reference"}], "read_word": 1})

    @unittest.skipUnless(alias.CHECKER.is_file(), "build the Lean alias checker")
    def test_kernel_accepts_actual_reference_transfer(self):
        self.assertTrue(alias.checked(self.candidate))

    @unittest.skipUnless(alias.CHECKER.is_file(), "build the Lean alias checker")
    def test_live_allocation_payload_and_overwrite_mutations_reject(self):
        original = "Dyn *d = gc_box(0); d->t = t; d->v = (I)p; return d;"
        for changed in (
                "Dyn *d = gc_box(1); d->t = t; d->v = (I)p; return d;",
                "Dyn *d = gc_box(0); d->t = t; d->v = 0; return d;",
                "Dyn *d = gc_box(0); d->t = t; d->v = (I)p; d->v = 0; return d;",
                "Dyn *d = gc_box(0); d->t = t; return d;"):
            with self.subTest(changed=changed):
                self.assertFalse(alias.checked(self.changed(original, changed)))

    @unittest.skipUnless(alias.CHECKER.is_file(), "build the Lean alias checker")
    def test_changed_allocator_branch_is_not_trusted(self):
        candidate = self.changed("return atomic ? pys_alloc_atomic(15) : pys_alloc(15);",
                                 "return atomic ? pys_alloc_atomic(15) : pys_alloc_atomic(15);")
        self.assertFalse(alias.checked(candidate))

    @unittest.skipUnless(alias.CHECKER.is_file(), "build the Lean alias checker")
    def test_same_width_runtime_field_swap_disagrees_with_lowering(self):
        # Keep the independent correspondence check even though changing the
        # real struct also invalidates positional scalar-box initializers.
        layout = alias.physical_layout(self.runtime)
        layout["tag"], layout["payload"] = layout["payload"], layout["tag"]
        with mock.patch.object(alias, "physical_layout", return_value=layout):
            self.assertFalse(alias.checked(alias.normalize_runtime(self.runtime)))

    def test_changed_extent_unknown_statement_and_pointer_arithmetic_fail_closed(self):
        for old, new in (
                ("return atomic ? pys_alloc_atomic(15) : pys_alloc(15);",
                 "return atomic ? pys_alloc_atomic(15) : pys_alloc(7);"),
                ("d->v = (I)p; return d;", "d->v = (I)p + 8; return d;"),
                ("d->v = (I)p; return d;", "d->v = (I)p; return NULL;"),
                ("if (!p) return DNONE;", "if (p) return DNONE;"),
                ("d->v = (I)p; return d;", "d->v = (int32_t)(I)p; return d;")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.changed(old, new)

    def test_field_width_and_word_typedef_are_not_assumed(self):
        for old, new in (("typedef int64_t I;", "typedef int32_t I;"),
                         ("struct Dyn { const DynType *t; I v; };",
                          "struct Dyn { const DynType *t; int32_t v; };")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.changed(old, new)

    def test_macro_scoped_payload_narrowing_uses_actual_translation_unit(self):
        declaration = "struct Dyn { const DynType *t; I v; };"
        with self.assertRaisesRegex(ValueError, "unsupported box word ABI"):
            self.changed(declaration, "#define I int32_t\n" + declaration + "\n#undef I")

    @unittest.skipUnless(alias.CHECKER.is_file(), "build the Lean alias checker")
    def test_changed_actual_payload_lowering_is_rejected(self):
        original = alias.gen_lower_ins

        def wrong_word(target, context, instruction):
            original(target, context, instruction)
            target.out[0] = target.out[0].replace("i64 1", "i64 0")

        with mock.patch.object(alias, "gen_lower_ins", wrong_word):
            self.assertFalse(alias.checked(alias.normalize_runtime(self.runtime)))


@unittest.skipUnless(alias.CHECKER.is_file(), "build the Lean alias checker")
class NativeAliasControls(unittest.TestCase):
    def test_missing_fields_unknown_sources_and_schema_downgrades_fail(self):
        original = {"schema_version": 1, "words": 2, "scanned": True,
                    "stores": [{"word": 0, "source": "tag"}, {"word": 1, "source": "reference"}],
                    "read_word": 1}
        for mode in ("missing", "schema", "source", "extra"):
            candidate = copy.deepcopy(original)
            if mode == "missing":
                del candidate["stores"]
            elif mode == "schema":
                candidate["schema_version"] = 0
            elif mode == "source":
                candidate["stores"][1]["source"] = "copied-object"
            else:
                candidate["trusted"] = True
            result = subprocess.run([str(alias.CHECKER)], input=json.dumps(candidate), text=True,
                                    capture_output=True, timeout=10)
            with self.subTest(mode=mode):
                self.assertEqual(result.returncode, 2)
                self.assertFalse(json.loads(result.stdout)["accepted"])

    def test_missing_and_overwritten_reference_stores_and_atomic_allocations_fail(self):
        for stores, scanned, words in (([], True, 2),
                                      ([{"word": 1, "source": "reference"}], False, 2),
                                      ([{"word": 1, "source": "reference"}], True, 1),
                                      ([{"word": 1, "source": "reference"},
                                        {"word": 1, "source": "tag"}], True, 2)):
            with self.subTest(stores=stores, scanned=scanned, words=words):
                self.assertFalse(alias.checked({"schema_version": 1, "words": words,
                                                "scanned": scanned, "stores": stores, "read_word": 1}))


if __name__ == "__main__":
    unittest.main()
