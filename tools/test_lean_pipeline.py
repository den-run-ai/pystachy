"""Actual stage-state correspondence and fail-closed inspection-report checks."""
import copy
from contextlib import redirect_stderr
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_pipeline as pipeline


ROOT = Path(__file__).resolve().parent.parent
CHECKER = pipeline.DEFAULT_CHECKER
if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not CHECKER.is_file():
    raise RuntimeError("Lean pipeline checker is required; build tools/lean_boundary first")
STAGES = list(pipeline.STAGES)
SOURCE = """def total(values: list[int]) -> int:
    result = 0
    for value in values:
        result += value
    return result

print(total([1, 2, 3]))
"""
RETRY = """total = 0
def add(value: float) -> None:
    global total
    total += value
add(1.5)
print(total)
"""


def serialized_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


class ReportFixtures:
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.reports = {}
        for label, source, flags in (("lower", SOURCE, []), ("finalize", SOURCE, ["--stop-after", "finalize"]),
                                     ("retry", RETRY, [])):
            path = cls.directory / f"{label}.py"
            path.write_text(source)
            output = cls.directory / label
            env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            env["PYSTACHY_HOME"] = str(ROOT)
            result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(path),
                                     "--output", str(output), "--typed-after-only", *flags],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            raw = (output / "typed-after.json").read_bytes()
            cls.reports[label] = (json.loads((output / "report.json").read_text()), json.loads(raw),
                                  hashlib.sha256(raw).hexdigest())

    def sample(self, name="lower"):
        return copy.deepcopy(self.reports[name])


class ReportShapeTests(ReportFixtures, unittest.TestCase):
    def test_actual_reports_normalize_requested_targets(self):
        for name, target in (("lower", 6), ("finalize", 5), ("retry", 6)):
            report, snapshot, digest = self.sample(name)
            candidate = pipeline.normalize(report, snapshot, digest)["report"]
            self.assertEqual(candidate["target"], target)
            self.assertEqual(candidate["attempts"][-1]["state"]["history"], list(range(1, target + 1)))
        self.assertGreater(len(self.reports["retry"][0]["attempts"]), 1)

    def test_snapshot_contents_are_bound_to_report(self):
        report, snapshot, digest = self.sample()
        snapshot["functions"].clear()
        with self.assertRaisesRegex(ValueError, "digest does not match"):
            pipeline.normalize(report, snapshot, serialized_hash(snapshot))
        del report["artifact_sha256"]
        with self.assertRaisesRegex(ValueError, "no typed-after artifact digest"):
            pipeline.normalize(report, snapshot, digest)

    def test_stage_inventory_cannot_be_silently_dropped(self):
        report, snapshot, digest = self.sample()
        report["attempts"][-1]["pipeline"]["stages"].pop()
        with self.assertRaisesRegex(ValueError, "pipeline stage inventory"):
            pipeline.normalize(report, snapshot, digest)

    def test_malformed_nested_mappings_fail_closed(self):
        for key in ("artifact_sha256", "artifacts", "settings", "input"):
            for value in (None, [], "invalid"):
                with self.subTest(key=key, value=value):
                    report, snapshot, digest = self.sample()
                    report[key] = value
                    with self.assertRaises(ValueError):
                        pipeline.normalize(report, snapshot, digest)

    def test_missing_source_or_verification_inventory_fails_closed(self):
        for key in ("modules", "sha256", "source_sha256"):
            report, snapshot, digest = self.sample()
            del report["input"][key]
            with self.assertRaises(ValueError):
                pipeline.normalize(report, snapshot, digest)
        report, snapshot, digest = self.sample()
        report["input"]["modules"] = []
        with self.assertRaisesRegex(ValueError, "source inventory"):
            pipeline.normalize(report, snapshot, digest)
        report, snapshot, digest = self.sample()
        report["input"]["path"] = "foreign.py"
        with self.assertRaisesRegex(ValueError, "absent from the consumed"):
            pipeline.normalize(report, snapshot, digest)
        for verification in (None, {}, {"requested": True, "completed": False}):
            report, snapshot, digest = self.sample()
            report["verification"] = verification
            with self.assertRaisesRegex(ValueError, "requested IR verification"):
                pipeline.normalize(report, snapshot, digest)

    def test_boolean_indices_and_unknown_status_are_malformed(self):
        for key, value in (("index", True), ("status", "success")):
            report, snapshot, digest = self.sample()
            report["attempts"][-1][key] = value
            with self.assertRaises(ValueError):
                pipeline.normalize(report, snapshot, digest)

    def test_finalize_must_be_explicit(self):
        report, snapshot, digest = self.sample("finalize")
        del report["settings"]["stop_after"]
        with self.assertRaisesRegex(ValueError, "lower target lacks"):
            pipeline.normalize(report, snapshot, digest)

    def test_target_cannot_hide_unexpected_llvm(self):
        report, snapshot, digest = self.sample()
        report["settings"]["stop_after"] = "finalize"
        with self.assertRaisesRegex(ValueError, "finalize target includes LLVM"):
            pipeline.normalize(report, snapshot, digest)

    def test_duplicate_json_report_keys_fail_closed(self):
        path = self.directory / "duplicate.json"
        path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            pipeline.bridge.read_snapshot(path)


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved pipeline checker")
class PipelineProofTests(ReportFixtures, unittest.TestCase):
    def accepted(self, report, snapshot, digest):
        fields, code = pipeline.check(report, snapshot, digest)
        self.assertEqual((fields["status"], code), ("accepted", 0), fields)
        self.assertTrue(fields["checked"])

    def rejected(self, report, snapshot, digest):
        fields, code = pipeline.check(report, snapshot, digest)
        self.assertEqual((fields["status"], code), ("rejected", 1), fields)

    def test_real_lower_finalize_and_retry_reports_are_accepted(self):
        for name in self.reports:
            with self.subTest(name=name):
                self.accepted(*self.sample(name))

    def test_completed_stage_reordering_duplication_and_omission_are_rejected(self):
        for history in (["discover", "prepare", *STAGES[2:]], ["prepare", "prepare", *STAGES[2:]], STAGES[1:]):
            report, snapshot, digest = self.sample()
            report["attempts"][-1]["pipeline"]["completed_stages"] = history
            self.rejected(report, snapshot, digest)

    def test_foreign_attempt_snapshot_and_reused_attempt_index_are_rejected(self):
        report, snapshot, _ = self.sample("retry")
        snapshot["attempt"] -= 1
        digest = serialized_hash(snapshot)
        report["artifact_sha256"]["typed-after"] = digest
        self.rejected(report, snapshot, digest)
        report, snapshot, digest = self.sample("retry")
        report["attempts"][-1]["index"] = report["attempts"][0]["index"]
        self.rejected(report, snapshot, digest)

    def test_incomplete_or_stale_terminal_state_is_rejected(self):
        for key, value in (("active_stage", "lower"), ("stage", "finalize"), ("status", "partial"),
                           ("source_provenance", "inconsistent")):
            report, snapshot, digest = self.sample()
            report["attempts"][-1]["pipeline"][key] = value
            self.rejected(report, snapshot, digest)

    def test_lost_or_forged_stage_evidence_is_rejected(self):
        for name, index, status in (("lower", 0, "unavailable"), ("finalize", 5, "completed")):
            report, snapshot, digest = self.sample(name)
            report["attempts"][-1]["pipeline"]["stages"][index]["status"] = status
            self.rejected(report, snapshot, digest)

    def test_failed_or_completed_preceding_attempt_is_rejected(self):
        for status in ("failed", "completed"):
            report, snapshot, digest = self.sample("retry")
            report["attempts"][0]["status"] = status
            self.rejected(report, snapshot, digest)

    def test_idle_trace_cannot_be_relabelled_as_an_aborted_retry(self):
        report, snapshot, digest = self.sample("retry")
        state = report["attempts"][0]["pipeline"]
        active = state["active_stage"]
        self.assertIsNotNone(active)
        state["active_stage"] = None
        next(item for item in state["stages"] if item["name"] == active)["status"] = "unavailable"
        self.rejected(report, snapshot, digest)

    def test_retry_cannot_cross_requested_finalization_boundary(self):
        report, snapshot, _ = self.sample("finalize")
        retry = copy.deepcopy(report["attempts"][0])
        retry["status"] = "retry"
        retry["pipeline"]["status"] = "partial"
        retry["pipeline"]["active_stage"] = "lower"
        for item in retry["pipeline"]["stages"]:
            item["status"] = "partial"
        report["attempts"].insert(0, retry)
        report["attempts"][1]["index"] = 2
        snapshot["attempt"] = 2
        digest = serialized_hash(snapshot)
        report["artifact_sha256"]["typed-after"] = digest
        self.rejected(report, snapshot, digest)

    def test_source_or_overall_failure_cannot_certify_pipeline(self):
        report, snapshot, digest = self.sample()
        report["input"]["changed_during_compilation"] = True
        self.rejected(report, snapshot, digest)
        report, snapshot, digest = self.sample()
        report["input"]["modules"][0]["changed_since_read"] = True
        self.rejected(report, snapshot, digest)
        report, snapshot, digest = self.sample()
        report["status"] = "error"
        self.rejected(report, snapshot, digest)

    def test_partial_snapshot_cannot_certify_pipeline(self):
        report, snapshot, _ = self.sample()
        snapshot["status"] = "partial"
        digest = serialized_hash(snapshot)
        report["artifact_sha256"]["typed-after"] = digest
        report["stages"][1]["status"] = "partial"
        self.rejected(report, snapshot, digest)

    def test_checker_response_count_and_exit_status_must_agree(self):
        report, snapshot, digest = self.sample()
        candidate = pipeline.normalize(report, snapshot, digest)
        checker = self.directory / "inconsistent-checker"
        for response in ({"accepted": True, "attempts": 0}, {"accepted": False, "attempts": 1}):
            checker.write_text("#!/usr/bin/env python3\nprint(" + repr(json.dumps(response)) + ")\n")
            checker.chmod(0o700)
            with self.assertRaises(ValueError):
                pipeline.invoke(candidate, checker)

    def test_all_reachable_python_states_and_actions_match_lean(self):
        # Thirteen reachable idle/active states, both methods, six valid names,
        # empty and unknown names: 208 independently evaluated transitions, and
        # a decision (PipelineState.decide) in each state: 221 in all.
        from src.pystachy_compiler.pipeline import PipelineState, STAGE_PREDECESSORS
        self.assertEqual(list(STAGE_PREDECESSORS), STAGES)
        self.assertEqual(list(STAGE_PREDECESSORS.values()), ["new", *STAGES[:-1]])
        numbers = {"": 0, "new": 0, **pipeline.STAGE_NUMBERS, "unknown": 7}

        def state(value):
            return {"stage": numbers[value.stage], "active": numbers[value.active],
                    "history": [numbers[name] for name in value.history]}

        decided = []
        current = PipelineState()
        states = [copy.deepcopy(current)]
        for name in STAGES:
            current.begin(name)
            states.append(copy.deepcopy(current))
            current.complete(name)
            states.append(copy.deepcopy(current))
        trials, expected = [], []
        for previous in states:
            for method in ("begin", "complete"):
                for name in ("", *STAGES, "unknown"):
                    current = copy.deepcopy(previous)
                    trials.append({"state": state(current), "kind": method, "stage": numbers[name]})
                    with redirect_stderr(StringIO()):
                        try:
                            getattr(current, method)(name)
                        except SystemExit as error:
                            self.assertEqual(error.code, 1)
                            self.assertEqual(state(current), state(previous), "rejected action mutated state")
                            expected.append(None)
                        else:
                            expected.append(state(current))
            current = copy.deepcopy(previous)
            trials.append({"state": state(current), "kind": "decide", "stage": 0})
            with redirect_stderr(StringIO()):
                try:
                    current.decide("a probe")
                except SystemExit as error:
                    self.assertEqual(error.code, 1)
                    expected.append(None)
                else:
                    expected.append(state(current))
            decided.append(expected[-1] is not None)
            self.assertEqual(state(current), state(previous), "a decision changed the stage state")
        self.assertEqual(len(trials), 221)
        self.assertEqual(decided, [True] * 4 + [False] * 9, "only the new, preparing, prepared and discovering states decide")
        result = subprocess.run([str(CHECKER)], input=json.dumps({"steps": trials}),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {"results": expected})


if __name__ == "__main__":
    unittest.main()
