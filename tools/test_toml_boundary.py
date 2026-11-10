"""Failure controls for the TOML boundary evidence runner."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("toml_boundary_report", ROOT / "bench/toml_boundary/run.py")
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


class TomlBoundaryEvidenceTests(unittest.TestCase):
    def test_output_requires_matching_checksum_exact_rows_and_positive_time(self):
        result = report.outputs({"stdout": "sample 75 1000\nsample 75 2000\n"}, 2, 75)
        self.assertEqual(result["in_process_samples_s"], [0.000001, 0.000002])
        for output, message in (
            ("sample 74 1000\n", "checksum"),
            ("sample 75 1000\nsample 75 2000\n", "number of output"),
            ("", "number of output"),
            ("sample 75 0\n", "nonpositive"),
            ("sample 75 -1\n", "nonpositive"),
        ):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, message):
                report.outputs({"stdout": output}, 1, 75)

    def test_summary_gives_each_process_equal_weight(self):
        # One very slow process has many correlated samples. Flattening all
        # samples would report 100; three independent process medians give 2.
        result = report.summarize_process_samples([
            {"in_process_samples_s": [1.0]},
            {"in_process_samples_s": [2.0]},
            {"in_process_samples_s": [100.0] * 101},
        ])
        self.assertEqual(result["median_s"], 2.0)
        self.assertEqual(result["mad_s"], 1.0)
        self.assertEqual(result["min_s"], 1.0)
        self.assertEqual(result["max_s"], 100.0)

    def test_retention_requires_both_checksums_and_live_bytes(self):
        result = report.retained_output({"stdout": "checksum 204\nretained 109185 102\n"}, 204, 2)
        self.assertEqual(result["conservative_live_bytes"], 109185)
        for output in (
            "checksum 203\nretained 109185 102\n",
            "checksum 204\nretained 109185 101\n",
            "checksum 204\nretained 0 102\n",
            "checksum 204\nretained 109185 102\nextra\n",
        ):
            with self.subTest(output=output), self.assertRaises(ValueError):
                report.retained_output({"stdout": output}, 204, 2)

    def test_manifest_sees_untracked_extensionless_inputs_and_root_glue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("pystachy.py", "pystachy_cli.py", "runtime.c", "lljit.c",
                         "tools/ir_cost_report.py", "lib/plain", "lib/pkg/extra.dat",
                         "lib/__pycache__/plain.pyc", "src/compiler.py"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("original\n")
            before = report.manifest(root)
            self.assertIn("lib/plain", before)
            self.assertIn("lib/pkg/extra.dat", before)
            self.assertIn("pystachy_cli.py", before)
            self.assertIn("lljit.c", before)
            self.assertNotIn("lib/__pycache__/plain.pyc", before)
            (root / "lib/plain").write_text("changed\n")
            after = report.manifest(root)
            self.assertNotEqual(before, after)
            self.assertNotEqual(before["lib/plain"], after["lib/plain"])
            (root / "lib/new_module").write_text("new input\n")
            self.assertIn("lib/new_module", report.manifest(root))

    def test_ir_inventory_excludes_mentions_and_separates_dispatchers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.ll"
            path.write_text("""declare void @pys_dyn_int()
declare void @dyn.call()
declare void @sink(ptr)
define void @main() {
  ; call void @pys_dyn_fake()
  call void @sink(ptr @pys_dyn_int)
  call void @pys_dyn_int()
  call void @dyn.call()
  ret void
}
""")
            result = report.inventory(path)
            self.assertEqual(result["dynamic_static_calls"], {"pys_dyn_int": 1})
            self.assertEqual(result["dynamic_static_calls_total"], 1)
            self.assertEqual(result["generated_dynamic_static_calls"], {"dyn.call": 1})


if __name__ == "__main__":
    unittest.main()
