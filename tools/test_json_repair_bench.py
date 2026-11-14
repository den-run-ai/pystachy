"""Fail-closed contract tests for JSON-repair paired timing evidence."""
import copy
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from json_repair_bench import digest, parse_output, run_campaign, run_process, validate_config, verify_input_identity
from json_repair_refresh import llvm_shared_library, make_configs, upstream_identity


class JsonRepairBenchTests(unittest.TestCase):
    def test_all_measured_and_warmup_batches_are_retained(self):
        output = "witness escaped 5 27 13 0\nrounds 2\nwarmup_seconds 0.7\nseconds 0.2\nseconds 0.4\n"
        evidence = parse_output(output, 2, 1)
        self.assertEqual(evidence["seconds"], [0.2, 0.4])
        self.assertEqual(evidence["warmup_seconds"], [0.7])
        self.assertAlmostEqual(evidence["median_seconds"], 0.3)
        self.assertEqual(evidence["witness"], ["witness escaped 5 27 13 0", "rounds 2"])

    def test_missing_extra_and_invalid_timings_fail(self):
        witness = "witness escaped 5 27 13 0\n"
        for output in ("seconds 0.1\n", witness, witness + "seconds 0.1\nseconds 0.2\n",
                       witness + "seconds nan\n", witness + "seconds inf\n",
                       witness + "seconds -0.1\n", witness + "seconds bad\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                parse_output(output, 1, 0)
        with self.assertRaises(ValueError):
            parse_output(witness + "seconds 0.1\n", 1, 1)

    def test_full_mixed_witness_keeps_output_and_checksum(self):
        output = 'outputs [{"ok": true}]\nper_round 1\nrecords 10\nchecksum 10\nseconds 0.1\n'
        evidence = parse_output(output, 1, 0)
        self.assertEqual(evidence["witness"], output.splitlines()[:-1])

    def config(self):
        return {"variants": [
            {"name": name, "source": str(Path(__file__).resolve().parents[1]),
             "commands": {"scaling": [sys.executable, "probe.py"]}}
            for name in ("before", "after")
        ], "cases": [{"name": "escape", "probe": "scaling", "args": ["escaped", "32", "1"]}]}

    def test_shell_commands_and_duplicate_names_are_rejected(self):
        valid = self.config()
        validate_config(valid)
        bad = copy.deepcopy(valid)
        bad["variants"][0]["commands"]["scaling"] = "python probe.py"
        with self.assertRaises(ValueError):
            validate_config(bad)
        bad = copy.deepcopy(valid)
        bad["variants"][1]["name"] = "before"
        with self.assertRaises(ValueError):
            validate_config(bad)
        bad = copy.deepcopy(valid)
        bad["cases"][0]["args"] = ["escaped", 32, 1]
        with self.assertRaises(ValueError):
            validate_config(bad)

    def test_indirect_fixture_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            fixture.write_text('{"expected": 1}\n')
            variant = {"input_sha256": {str(fixture): digest(fixture)}}
            self.assertEqual(verify_input_identity(variant), variant["input_sha256"])
            fixture.write_text('{"expected": 2}\n')
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                verify_input_identity(variant)

    def test_indirect_inputs_require_existing_absolute_paths_and_hashes(self):
        for declared in (["fixture.json"], {"fixture.json": "0" * 64}, {"/missing/fixture.json": "x"}):
            config = self.config()
            config["variants"][0]["input_sha256"] = declared
            with self.subTest(declared=declared), self.assertRaisesRegex(ValueError, "input_sha256"):
                validate_config(config)

    def test_campaign_rechecks_indirect_inputs_after_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.json"
            fixture.write_text("before")
            config = self.config()
            for variant in config["variants"]:
                variant["commands"] = {"scaling": [sys.executable]}
                variant["input_sha256"] = {str(fixture): digest(fixture)}

            def mutate(*args):
                fixture.write_text("after")
                return {"stdout": "witness exact\nseconds 0.1\n", "whole_process_peak_rss_bytes": 1}

            with patch("json_repair_bench.source_identity", return_value={}), \
                    patch("json_repair_bench.run_process", side_effect=mutate), \
                    self.assertRaisesRegex(ValueError, "inputs changed"):
                run_campaign(config, pairs=1, batches=1, warmups=0, cpu=0, timeout=5)

    def test_refresh_rejects_the_wrong_upstream_revision(self):
        with patch("json_repair_refresh.git", return_value="wrong"):
            with self.assertRaisesRegex(ValueError, "pinned manifest commit"):
                upstream_identity(Path("/unused"))

    def test_refresh_configs_cover_all_three_consumers_and_extension_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("bench", "facade", "scaling", "schema"):
                (root / name).write_bytes(b"not executed by this configuration test")
            package = root / "pystachy_json_repair"
            package.mkdir()
            (package / "__init__.py").write_text("# companion\n")
            extension = package / "_native.abi3.so"
            extension.write_bytes(b"extension identity sentinel")
            with patch.dict(os.environ, {"PYSTACHY_LLVM": "/llvm/bin", "LD_LIBRARY_PATH": "/llvm/lib"}), \
                    patch("json_repair_refresh.upstream_identity", return_value={"source_sha256": {}}), \
                    patch("json_repair_refresh.python_identity", return_value=({}, {})), \
                    patch("json_repair_refresh.llvm_identity", return_value=({}, {})):
                configs = make_configs(upstream=root, python=Path(sys.executable),
                                       native_dir=root, companion_dir=root)
            self.assertEqual({name: len(config["cases"]) for name, config in configs.items()},
                             {"repair": 7, "schema": 8, "companion": 6})
            self.assertEqual(len(configs["repair"]["variants"]), 4)
            self.assertEqual(len(configs["schema"]["variants"]), 4)
            companion = configs["companion"]["variants"][1]
            self.assertEqual(companion["input_sha256"][str(extension)], digest(extension))
            self.assertIn(str(Path(__file__).resolve().parents[1] / "pyext.c"), companion["input_sha256"])
            self.assertIn(str(Path(__file__).resolve().parents[1] / "lljit.c"),
                          configs["repair"]["variants"][3]["input_sha256"])
            upstream_schema = configs["schema"]["variants"][0]["commands"]["schema"]
            self.assertTrue(upstream_schema[-1].endswith("schema_upstream.py"))

    def test_llvm_library_mapping_tracks_resolved_bytes_and_rejects_ambiguity(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / "actual.so"
            library.write_bytes(b"selected LLVM")
            link = Path(directory) / "libLLVM.so"
            link.symlink_to(library)
            mapping = f"\tlibLLVM.so.18.1 => {link} (0xabc123)\n"
            with patch("json_repair_refresh.shutil.which", return_value="/usr/bin/ldd"), \
                    patch("json_repair_refresh.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess([], 0, mapping, "")
                with patch.dict(os.environ, {"LD_LIBRARY_PATH": "/measured/loader"}):
                    identity = llvm_shared_library("/selected/lli")
                self.assertEqual(identity, {"path": str(link), "realpath": str(library), "sha256": digest(library)})
                self.assertEqual(run.call_args.kwargs["env"]["LD_LIBRARY_PATH"], "/measured/loader")
                for output in ("", mapping + mapping, "libLLVM.so => not found\n"):
                    run.return_value = subprocess.CompletedProcess([], 0, output, "")
                    with self.subTest(output=output), self.assertRaises(ValueError):
                        llvm_shared_library("/selected/lli")

    @unittest.skipUnless(hasattr(os, "wait4"), "requires POSIX wait4")
    def test_child_exit_and_memory_are_recorded(self):
        result = run_process([sys.executable, "-c", "print('witness smoke'); print('seconds 0.1')"],
                             dict(os.environ), 5)
        self.assertGreater(result["whole_process_peak_rss_bytes"], 0)
        self.assertEqual(parse_output(result["stdout"], 1, 0)["seconds"], [0.1])
        with self.assertRaises(RuntimeError):
            run_process([sys.executable, "-c", "raise SystemExit(2)"], dict(os.environ), 5)


if __name__ == "__main__":
    unittest.main()
