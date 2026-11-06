"""Small artificial records test analysis math and evidence validation, not performance."""
import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("gc_application_summarize", Path(__file__).with_name("summarize.py"))
# Exact diagnostic from bdwgc-contract-manual-vdb.json's default integration
# probe. It supplies a parser fixture only, not workload performance evidence.
BDW_LINE = ("bdwgc: version=8.2.6 mode=default incremental=0 protection=1 markers=1 "
            "collections=2724 stopped_world_ms=34.843 pauses=2724 heap_peak_bytes=495616 "
            "heap_bytes=20480 free_bytes=0 allocated_bytes=435090304\n")
SUMMARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUMMARY)


def fixture():
    variants = [{"name": n, "argv": ["/same/binary", "arg"], "env": {"PYSTACHY_GC": "stats"},
                 "executable_sha256": "same", "inputs_sha256": {}, "cwd": "/same", "address_space_mib": 2048}
                for n in ("main", "main_aa", "scalar")]
    samples = []
    for phase, count in (("warmup", 1), ("measure", 3)):
        for rnd in range(count):
            for variant in variants:
                wall = 10000 if phase == "warmup" else [1, 10, 10][rnd]
                if phase == "measure" and variant["name"] == "scalar":
                    wall = [3, 3, 30][rnd]
                samples.append({"variant": variant["name"], "phase": phase, "round": rnd,
                                "returncode": 0, "output_matches": True, "stdout_sha256": "output", "artifact_sha256": None,
                                "wall_s": wall, "user_s": wall, "system_s": 0, "peak_rss_kib": 1024,
                                "gc_reports": [{"elapsed_ms": 0, "collections": 0, "heap_peak_mib": 1, "last_live_mib": 0}]})
    return {"complete": True, "all_outputs_match": True, "variants": variants, "samples": samples,
            "rounds": 3, "warmups": 1, "cpu": 3, "workload": "artificial-test"}


class SummaryTests(unittest.TestCase):
    def test_pairs_precede_medians_and_warmups_are_excluded(self):
        result = SUMMARY.summarize(fixture())
        row = next(c for c in result["comparisons"] if c["candidate"] == "scalar")
        self.assertEqual(row["wall"]["paired"], [3, 0.3, 3])
        self.assertEqual(row["wall"]["median"], 3)
        self.assertAlmostEqual(row["wall"]["geometric_mean"], 2.7 ** (1 / 3))
        self.assertEqual(result["variants"]["scalar"]["wall_s_median"], 3)
        self.assertIsNone(row["gc_ratio"])
        self.assertEqual(result["aa"]["max_absolute_paired_pct"], 0)

    def test_missing_duplicate_or_corrupt_sample_rejects(self):
        base = fixture()
        for mutation in ("missing", "duplicate", "output", "artifact", "incomplete"):
            value = copy.deepcopy(base)
            if mutation == "missing":
                value["samples"].pop()
            elif mutation == "duplicate":
                value["samples"].append(value["samples"][-1])
            elif mutation == "output":
                value["samples"][-1]["stdout_sha256"] = "different"
            elif mutation == "artifact":
                for v in value["variants"]:
                    v["argv"].append("{output}")
            else:
                value["complete"] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                SUMMARY.summarize(value)

    def test_bdw_metrics_are_separate_from_native_gc(self):
        value = fixture()
        for row in value["samples"]:
            row["gc_reports"] = []
            row["stderr_tail"] = BDW_LINE
        result = SUMMARY.summarize(value)
        summary = result["variants"]["main"]
        self.assertEqual(summary["bdw_mode"], "default")
        self.assertEqual(summary["bdw_markers"], 1)
        self.assertEqual(summary["bdw_collections_median"], 2724)
        self.assertEqual(summary["bdw_stopped_world_ms_median"], 34.843)
        self.assertEqual(summary["bdw_heap_peak_bytes_median"], 495616)
        self.assertEqual(summary["bdw_allocated_bytes_median"], 435090304)
        self.assertNotIn("gc_elapsed_ms_median", summary)
        self.assertNotIn("gc_share_pct_median", summary)
        for field, changed in (("mode=default", "mode=incremental"), ("markers=1", "markers=2"),
                               ("incremental=0", "incremental=1"), ("protection=1", "protection=0")):
            altered = copy.deepcopy(value)
            altered["samples"][-1]["stderr_tail"] = BDW_LINE.replace(field, changed)
            with self.subTest(field=field), self.assertRaises(ValueError):
                SUMMARY.summarize(altered)

    def test_nonidentical_aa_or_changed_memory_budget_rejects(self):
        for key, changed in (("executable_sha256", "different"), ("env", {}), ("address_space_mib", 1024)):
            value = fixture()
            value["variants"][1][key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                SUMMARY.summarize(value)


if __name__ == "__main__":
    unittest.main()
