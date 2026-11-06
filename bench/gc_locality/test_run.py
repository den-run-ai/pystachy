"""Correctness checks for the research controller; no runtime performance gates."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("gc_locality_run", HERE / "run.py")
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)

STATS = "gc: 3 collections, 2.5 ms; heap peak 4.0 MiB; live 1.0 MiB at the last"
PHASES = "gc phases: roots 0.125 ms; trace 2.000 ms; sweep 0.375 ms"
WORK = "gc work: root words 21; heap words 12345678901; scanned objects 7; range pushes 8; chunk visits 9"


class DiagnosticTests(unittest.TestCase):
    def test_native_and_optional_gc_environment_is_explicit(self):
        inherited = {"PYSTACHY_GC": "off", "GC_DONT_GC": "1", "GC_INITIAL_HEAP_SIZE": "999999999",
                     "LD_PRELOAD": "bad", "PYTHONPATH": "bad", "PYTHONHOME": "bad", "PATH": "/bin"}
        with patch.dict(os.environ, inherited, clear=True):
            self.assertEqual(RUN.environment({"GC_INITIAL_HEAP_SIZE": "1048576"}),
                             {"PATH": "/bin", "GC_INITIAL_HEAP_SIZE": "1048576"})

    def test_changed_validated_executable_is_rejected_before_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp, "program")
            executable.write_bytes(b"original executable")
            expected = RUN.digest(executable)
            variant = {"name": "a", "argv": [str(executable)], "validated_executable_sha256": expected}
            self.assertEqual(RUN.describe(variant, {})["executable_sha256"], expected)
            executable.write_bytes(b"replaced executable")
            with self.assertRaisesRegex(ValueError, "differs from validated build"):
                RUN.describe(variant, {})

    def test_address_space_limit_requires_a_positive_integer(self):
        variant = {"name": "a", "argv": [sys.executable]}
        for limit in (0, -1, True, "2048", 1.5, None):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    RUN.describe(variant, {"address_space_mib": limit})
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    RUN.describe(dict(variant, address_space_mib=limit), {"address_space_mib": 2048})

    def test_relative_and_empty_path_entries_use_variant_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            for entry in ("bin", ""):
                target = cwd / entry / "gc-relative-path-probe"
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(b"#!/bin/sh\n# " + entry.encode() + b"\n")
                target.chmod(0o755)
                description = RUN.describe({"name": "a", "cwd": str(cwd),
                                            "env": {"PATH": entry}, "argv": [target.name]}, {})
                self.assertEqual(description["executable_path"], str(target.resolve()))
                self.assertEqual(description["executable_sha256"], RUN.digest(target))

    def test_profile_records_remain_separate_from_stats(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write((STATS + "\n" + PHASES + "\n" + WORK + "\n" + STATS + "\n").encode())
            f.flush()
            lines, reports, profile, tail = RUN.diagnostics(f.name)
        self.assertEqual(len(reports), 2)
        self.assertEqual(reports[0], {"collections": 3, "elapsed_ms": 2.5,
                                      "heap_peak_mib": 4.0, "last_live_mib": 1.0})
        self.assertEqual(profile["phases"], [{"roots_ms": 0.125, "trace_ms": 2.0, "sweep_ms": 0.375}])
        self.assertEqual(profile["work"], [{"root_words": 21, "heap_words": 12345678901,
                                           "scanned_objects": 7, "range_pushes": 8, "chunk_visits": 9}])
        self.assertIn(PHASES, lines)
        self.assertIn(WORK, tail)

    def test_summary_excludes_warmup_and_ambiguous_gc_reports(self):
        def sample(phase, n, reports):
            return dict.fromkeys(RUN.METRICS, n) | {
                "phase": phase, "variant": "a", "output_matches": True, "gc_reports": reports}
        report = {"collections": 3, "elapsed_ms": 2.5, "heap_peak_mib": 4.0, "last_live_mib": 1.0}
        samples = [sample("warmup", 10000, [report]), sample("measure", 2, [report]),
                   sample("measure", 4, [report, report])]
        summary = RUN.summary(samples, ["a"])["a"]
        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["wall_s"], 3)
        self.assertNotIn("gc_elapsed_ms", summary)
        self.assertNotIn("gc_profile", summary)


@unittest.skipUnless(platform.system() == "Linux" and hasattr(os, "sched_getaffinity")
                     and hasattr(os, "wait4"), "controller requires Linux affinity and wait4")
class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.cpu = min(os.sched_getaffinity(0))
        self.config = self.work / "config.json"
        self.result = self.work / "result.json"
        self.code = ("import os,sys; from pathlib import Path; "
                     f"assert os.sched_getaffinity(0)=={{{self.cpu}}}; "
                     'assert "PYSTACHY_GC_STRESS" not in os.environ; '
                     'Path(sys.argv[1]).write_bytes(b"x"*2097152); print("checksum 42"); '
                     f"print({STATS!r},file=sys.stderr); print({PHASES!r},file=sys.stderr); "
                     f"print({WORK!r},file=sys.stderr)")

    def invoke(self, other=None, rounds=1, warmups=0, common=None, variant_b=None):
        config = {"name": "controller-test", "cwd": str(self.work), "variants": [
            {"name": "a", "argv": [sys.executable, "-c", self.code, "{output}"]},
            {"name": "b", "argv": [sys.executable, "-c", other or self.code, "{output}"]}]}
        config.update(common or {})
        config["variants"][1].update(variant_b or {})
        self.config.write_text(json.dumps(config))
        p = subprocess.run([sys.executable, "-I", str(HERE / "run.py"),
                            "--config", str(self.config), "--cpu", str(self.cpu),
                            "--rounds", str(rounds), "--warmups", str(warmups), "--json", str(self.result)],
                           env=dict(os.environ, PYSTACHY_GC_STRESS="1"), capture_output=True, text=True)
        self.assertTrue(self.result.is_file(), p.stderr)
        return p, json.loads(self.result.read_text())

    def test_child_observes_common_limit_and_variant_override(self):
        hard = resource.getrlimit(resource.RLIMIT_AS)[1]
        if hard != resource.RLIM_INFINITY and hard < 2048 * 1048576:
            self.skipTest("inherited address-space hard limit is below the fixture's 2 GiB cap")
        original = self.code
        self.code += ("; import resource; assert resource.getrlimit(resource.RLIMIT_AS) == "
                      f"{(2048 * 1048576,) * 2!r}")
        other = original + ("; import resource; assert resource.getrlimit(resource.RLIMIT_AS) == "
                            f"{(1536 * 1048576,) * 2!r}")
        p, report = self.invoke(other, common={"address_space_mib": 2048},
                                variant_b={"address_space_mib": 1536})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(report["all_outputs_match"])
        self.assertEqual([v["address_space_mib"] for v in report["variants"]], [2048, 1536])

    def test_no_configured_limit_preserves_inherited_limits(self):
        inherited = resource.getrlimit(resource.RLIMIT_AS)
        self.code += ("; import resource; assert resource.getrlimit(resource.RLIMIT_AS) == "
                      f"{inherited!r}")
        p, report = self.invoke()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual([v["address_space_mib"] for v in report["variants"]], [None, None])

    def test_checks_hashes_affinity_environment_and_rotating_order(self):
        p, report = self.invoke(rounds=2, warmups=1)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(report["complete"] and report["all_outputs_match"])
        self.assertEqual([s["variant"] for s in report["samples"]], ["a", "b", "a", "b", "b", "a"])
        self.assertEqual(report["summary"]["a"]["samples"], 2)
        self.assertEqual(report["summary"]["b"]["gc_elapsed_ms"], 2.5)
        expected = hashlib.sha256(b"x" * 2097152).hexdigest()
        for sample in report["samples"]:
            self.assertEqual(sample["artifact_bytes"], 2097152)
            self.assertEqual(sample["artifact_sha256"], expected)
            self.assertEqual(sample["stdout_sha256"], hashlib.sha256(b"checksum 42\n").hexdigest())
            self.assertEqual(sample["gc_profile"]["work"][0]["chunk_visits"], 9)

    def test_stdout_mismatch_stops_and_preserves_partial_results(self):
        p, report = self.invoke(self.code.replace("checksum 42", "checksum 43"), rounds=2)
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(report["complete"] or report["all_outputs_match"])
        self.assertEqual(len(report["samples"]), 2)
        self.assertFalse(report["samples"][-1]["output_matches"])

    def test_nonzero_exit_is_rejected_even_with_matching_outputs(self):
        p, report = self.invoke(self.code + "; sys.exit(7)")
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(report["all_outputs_match"])
        self.assertEqual(report["samples"][-1]["returncode"], 7)

    def test_missing_or_changed_artifact_is_rejected(self):
        for other in (self.code.replace('write_bytes(b"x"*2097152)', 'write_bytes(b"y"*2097152)'),
                      self.code + "; Path(sys.argv[1]).unlink()"):
            with self.subTest(code=other):
                p, report = self.invoke(other)
                self.assertNotEqual(p.returncode, 0)
                self.assertFalse(report["complete"] or report["all_outputs_match"])
                self.assertFalse(report["samples"][-1]["output_matches"])


if __name__ == "__main__":
    unittest.main()
