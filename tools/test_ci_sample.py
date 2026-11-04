"""Sparse PR selection preserves representative drivers and every changed fixture."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import ci_sample


class SampleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.write("tests/corpus.sh", (ci_sample.ROOT / "tests/corpus.sh").read_text())

    def write(self, name, text="print(1)\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return name

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True,
                              text=True, check=True, timeout=20).stdout.strip()

    def commit(self):
        self.git("init", "-q")
        self.git("add", "tests")
        self.git("-c", "user.email=ci@example.invalid", "-c", "user.name=CI", "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_exact_corpus_order_and_areas_with_bounded_lightweight_choices(self):
        files = [self.write(f"tests/programs/{area}/{name}.py") for area in ("z", "a")
                 for name in ("same_a", "same_b", "huge_suite")]
        errors = [self.write(f"tests/errors/{area}/reject.py", "# error: reject.py:1: unsupported\n")
                  for area in ("z", "a")]
        deviation = self.write("tests/deviations/basic.py")
        self.write("tests/programs/misplaced.py")
        self.write("tests/a_helper.py")
        self.write("tests/case_weights.txt", "default program 100\n" + "\n".join(
            f"{90000 if 'huge_suite' in name else 100} {name}" for name in files))
        selected = ci_sample.select_cases(self.root)
        self.assertEqual(selected, [name for name in ci_sample.corpus(self.root)
                                    if name in set(files + errors + [deviation]) and "huge_suite" not in name])
        self.assertEqual(len(selected), 7)
        self.assertEqual(ci_sample.select_cases(self.root), selected)

    def test_driver_strata_are_kept_even_outside_area_representatives(self):
        for name in ("cheap_a", "cheap_b"):
            self.write(f"tests/programs/area/{name}.py")
        expected = set()
        for sidecar in ("in", "full", "path"):
            name = self.write(f"tests/programs/area/driver_{sidecar}.py")
            self.write(name.removesuffix(".py") + "." + sidecar, "tests\n")
            expected.add(name)
        expected.add(self.write("tests/programs/area/signal.py", "# kill -INT\n"))
        expected.add(self.write("tests/programs/area/ffi.py", "import ffi\n"))
        expected.add(self.write("tests/programs/area/syntax_valid.py"))
        expected.add(self.write("tests/errors/area/syntax_invalid.py",
                                "# error: syntax_invalid.py:1: unsupported\n"))
        self.write("tests/case_weights.txt", "default program 9000\n100 tests/programs/area/cheap_a.py\n"
                   "101 tests/programs/area/cheap_b.py\n")
        self.assertTrue(expected.issubset(ci_sample.select_cases(self.root)))

    def test_changed_and_new_cases_sidecars_and_helper_imports_are_added(self):
        for name in ("basic_a", "basic_b", "changed", "output", "consumer"):
            self.write(f"tests/programs/area/{name}.py", "from helper import value\n" if name == "consumer"
                       else "print(1)\n")
        self.write("tests/programs/area/consumer.path", "tests\n")
        self.write("tests/helper.py", "value = 1\n")
        self.write("tests/programs/area/output.out", "1\n")
        self.write("tests/case_weights.txt", "default program 9000\n100 tests/programs/area/basic_a.py\n"
                   "101 tests/programs/area/basic_b.py\n")
        base = self.commit()
        self.write("tests/programs/area/changed.py", "print(2)\n")
        self.write("tests/programs/area/new.py", "print(3)\n")
        self.write("tests/programs/area/output.out", "2\n")
        self.write("tests/helper.py", "value = 2\n")
        chosen = ci_sample.select_cases(self.root, base)
        for name in ("changed", "new", "output", "consumer"):
            self.assertIn(f"tests/programs/area/{name}.py", chosen)
        evidence = ci_sample.manifest(self.root, base)
        self.assertEqual(evidence["base_commit"], base)
        self.assertEqual(evidence["cases"], chosen)
        self.assertEqual(evidence["selector"], ci_sample.SELECTOR)

    def test_deleted_sidecars_keep_surviving_cases_without_readding_deleted_programs(self):
        for name in ("basic_a", "basic_b", "deleted"):
            self.write(f"tests/programs/area/{name}.py")
        affected = set()
        sidecars = []
        for suffix in (".out", ".err", ".in", ".full", ".path"):
            case = self.write(f"tests/programs/area/changed_{suffix[1:]}.py")
            affected.add(case)
            sidecars.append(self.root / self.write(case.removesuffix(".py") + suffix, "fixture\n"))
        self.write("tests/case_weights.txt", "default program 9000\n100 tests/programs/area/basic_a.py\n"
                   "101 tests/programs/area/basic_b.py\n")
        base = self.commit()
        for path in sidecars:
            path.unlink()
        (self.root / "tests/programs/area/deleted.py").unlink()
        self.assertEqual(ci_sample.changed_cases(self.root, ci_sample.corpus(self.root), base), affected)
        chosen = ci_sample.select_cases(self.root, base)
        self.assertTrue(affected.issubset(chosen))
        self.assertNotIn("tests/programs/area/deleted.py", chosen)

    def test_deleted_helpers_keep_their_direct_consumers(self):
        for name in ("basic_a", "basic_b"):
            self.write(f"tests/programs/area/{name}.py")
        self.write("tests/programs/area/basic_a.path", "tests\n")
        affected = set()
        for name in ("helper", "helper_package"):
            case = self.write(f"tests/programs/area/{name}_consumer.py", f"from {name} import value\n")
            self.write(case.removesuffix(".py") + ".path", "tests\n")
            affected.add(case)
        helpers = [self.root / self.write(name, "value = 1\n")
                   for name in ("tests/helper.py", "tests/helper_package/__init__.py")]
        self.write("tests/case_weights.txt", "default program 9000\n100 tests/programs/area/basic_a.py\n"
                   "101 tests/programs/area/basic_b.py\n")
        base = self.commit()
        self.assertTrue(affected.isdisjoint(ci_sample.select_cases(self.root, base)))
        for path in helpers:
            path.unlink()
        self.assertEqual(ci_sample.changed_cases(self.root, ci_sample.corpus(self.root), base), affected)
        self.assertTrue(affected.issubset(ci_sample.select_cases(self.root, base)))

    def test_moved_sidecars_select_both_surviving_cases(self):
        for name in ("basic_a", "basic_b", "old", "new"):
            self.write(f"tests/programs/area/{name}.py")
        old = "tests/programs/area/old.out"
        new = "tests/programs/area/new.out"
        self.write(old, "fixture\n")
        self.write("tests/case_weights.txt", "default program 9000\n100 tests/programs/area/basic_a.py\n"
                   "101 tests/programs/area/basic_b.py\n")
        base = self.commit()
        self.git("config", "diff.renames", "true")
        self.git("mv", old, new)
        self.assertEqual(self.git("diff", "--name-status", base), f"R100\t{old}\t{new}")
        affected = {"tests/programs/area/old.py", "tests/programs/area/new.py"}
        self.assertEqual(ci_sample.changed_cases(self.root, ci_sample.corpus(self.root), base), affected)
        self.assertTrue(affected.issubset(ci_sample.select_cases(self.root, base)))

    def test_invalid_base_empty_corpus_and_duplicate_inventory_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "nonempty"):
            ci_sample.select_cases(self.root)
        self.write("tests/programs/area/basic.py")
        self.commit()
        for base in ("", "missing-branch", "--help"):
            with self.subTest(base=base), self.assertRaises(ValueError):
                ci_sample.select_cases(self.root, base)
        self.write("tests/corpus.sh", "corpus() { printf '%s\\n' tests/programs/area/basic.py tests/programs/area/basic.py; }\n")
        with self.assertRaisesRegex(ValueError, "unique"):
            ci_sample.select_cases(self.root)

    def test_stale_and_invalid_weight_rows_do_not_remove_cases(self):
        names = [self.write(f"tests/programs/area/{name}.py") for name in ("a", "b", "c")]
        self.write("tests/case_weights.txt", "default program 55\ndefault rejection -1\n"
                   f"-1 {names[0]}\n1234567890 {names[1]}\n9 nonexistent.py\n4 {names[2]}\n")
        self.assertEqual(ci_sample.case_weights(self.root, names), {names[0]: 55, names[1]: 55, names[2]: 4})
        self.assertEqual(set(ci_sample.select_cases(self.root)), {names[0], names[2]})

    def test_check_counts_include_syntax_checks_and_single_rejections(self):
        cases = [self.write("tests/programs/area/plain.py"), self.write("tests/programs/area/syntax_good.py"),
                 self.write("tests/deviations/deviation.py"),
                 self.write("tests/errors/area/syntax_self.py", "# error: syntax_self.py:1: broken\n"),
                 self.write("tests/errors/area/syntax_import.py", "# error: other.py:1: broken\n"),
                 self.write("tests/errors/area/plain.py", "# error: plain.py:1: broken\n")]
        self.assertEqual(ci_sample.expected_checks(cases, root=self.root), 11)
        self.assertEqual(ci_sample.expected_checks(cases, ("jit",), root=self.root), 8)
        with self.assertRaises(ValueError):
            ci_sample.expected_checks([], root=self.root)

    def test_cli_base_environment_and_program_filter(self):
        program = self.write("tests/programs/area/basic.py")
        self.write("tests/errors/area/basic.py")
        output, evidence = self.root / "cases", self.root / "manifest.json"
        real_manifest = ci_sample.manifest(self.root)
        with patch.dict(os.environ, {"CI_BASE_SHA": "my-base"}), patch.object(
                ci_sample, "manifest", return_value=real_manifest) as select:
            self.assertEqual(ci_sample.main(["--programs-only", "--output", str(output),
                                             "--manifest", str(evidence)]), 0)
        select.assert_called_once_with(base="my-base")
        self.assertEqual(output.read_text(), program + "\n")
        filtered = json.loads(evidence.read_text())
        self.assertEqual(filtered["cases"], [program])
        self.assertTrue(filtered["programs_only"])
        self.assertEqual(filtered["base_commit"], real_manifest["base_commit"])


class RepositorySampleTests(unittest.TestCase):
    def test_sample_is_small_covers_every_area_and_keeps_named_safety_smokes(self):
        cases = ci_sample.corpus()
        chosen = ci_sample.select_cases()
        self.assertTrue(set(ci_sample.SMOKE_CASES).issubset(cases), "renamed safety smoke: update selector explicitly")
        self.assertTrue(set(ci_sample.SMOKE_CASES).issubset(chosen))
        self.assertEqual({str(Path(name).parent) for name in cases},
                         {str(Path(name).parent) for name in chosen})
        self.assertGreaterEqual(len(chosen), 60)
        self.assertLessEqual(len(chosen), 150, "keep the baseline sparse; changed PR cases are additional")
        self.assertEqual(chosen, [name for name in cases if name in set(chosen)])
        self.assertGreater(ci_sample.expected_checks(chosen), len(chosen))


if __name__ == "__main__":
    unittest.main()
