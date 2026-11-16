#!/usr/bin/env python3
"""Check an inspection report's stage sequence and snapshot association with Lean.

The report and snapshot are observations from the trusted Python exporter. This
does not prove stage semantics, source/LLVM equivalence, or Python object ownership.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import check_lean_boundary as bridge


DEFAULT_CHECKER = bridge.ROOT / "tools/lean_boundary/.lake/build/bin/pystachy-pipeline"
STAGES = ("prepare", "discover", "analyze", "optimize", "finalize", "lower")
STAGE_NUMBERS = {name: index + 1 for index, name in enumerate(STAGES)}
EVIDENCE = {"unavailable": 0, "partial": 1, "completed": 2}
ATTEMPT_STATUS = {"failed": 0, "retry": 1, "completed": 2}
LIMITATIONS = [
    "Checks the recorded stage sequence, terminal target and snapshot-attempt association.",
    "The exporter, JSON bridge, reported source provenance and native Lean executable are trusted.",
    "Stage bodies, typing/specialization, representation correctness, IR semantics and LLVM lowering are not proved.",
    "The snapshot digest binds contents to this report; it does not authenticate the report or prove Python object ownership.",
]
require = bridge.require


def natural(value, what):
    require(type(value) is int and 0 <= value <= 65536, f"invalid {what}")
    return value


def boolean(value, what):
    require(type(value) is bool, f"invalid {what}")
    return value


def choice(value, choices, what):
    require(type(value) is str and value in choices, f"invalid {what}")
    return choices[value]


def digest(value, what):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), f"invalid {what}")
    return value


def normalize(report, snapshot, snapshot_sha256):
    """Project real report fields; stage facts are checked by Lean, not inferred here."""
    require(isinstance(report, dict) and isinstance(snapshot, dict), "report and snapshot must be objects")
    require(type(report.get("schema_version")) is int and report["schema_version"] == 1,
            "expected inspection report schema_version 1")
    require(type(snapshot.get("schema_version")) is int and snapshot["schema_version"] == 1,
            "expected inspection snapshot schema_version 1")
    require(snapshot.get("stage") == "typed-after", "expected typed-after snapshot")
    manifest = report.get("artifact_sha256")
    require(isinstance(manifest, dict), "report has no typed-after artifact digest; regenerate inspection")
    recorded_hash = manifest.get("typed-after")
    require(type(recorded_hash) is str and re.fullmatch(r"[0-9a-f]{64}", recorded_hash),
            "report has no typed-after artifact digest; regenerate inspection")
    require(type(snapshot_sha256) is str and recorded_hash == snapshot_sha256,
            "typed-after snapshot digest does not match the report")
    artifacts = report.get("artifacts")
    require(isinstance(artifacts, dict) and artifacts.get("typed-after") == "typed-after.json",
            "report has no typed-after artifact")
    settings = report.get("settings")
    require(isinstance(settings, dict), "report has no settings")
    target = choice(settings.get("stop_after", "lower"), {"finalize": 5, "lower": 6}, "stop_after target")
    stages = report.get("stages")
    require(isinstance(stages, list) and all(isinstance(stage, dict) for stage in stages),
            "invalid report stages")
    require([stage.get("name") for stage in stages] == ["typed-before", "typed-after", "llvm"],
            "invalid report stage inventory")
    require(stages[1].get("artifact") == "typed-after.json", "snapshot is not the recorded artifact")
    require(stages[1].get("status") == snapshot.get("status"), "snapshot/report evidence differs")
    if target == 5:
        require(stages[2].get("status") == "skipped" and stages[2].get("artifact") is None
                and "llvm" not in artifacts, "finalize target includes LLVM output")
    else:
        require(stages[2].get("status") == "completed" and stages[2].get("artifact") == "llvm.ll"
                and artifacts.get("llvm") == "llvm.ll", "lower target lacks complete LLVM output")
    source = report.get("input")
    require(isinstance(source, dict), "report has no input provenance")
    source_path = source.get("path")
    require(type(source_path) is str and source_path and "\0" not in source_path, "invalid input path")
    source_hash = digest(source.get("sha256"), "input digest")
    consumed_hash = digest(source.get("source_sha256"), "consumed input digest")
    changed = boolean(source.get("changed_during_compilation"), "source change flag")
    modules = source.get("modules")
    require(isinstance(modules, list) and modules, "invalid source inventory")
    input_recorded = False
    for module in modules:
        require(isinstance(module, dict), "invalid source module")
        path = module.get("path")
        require(type(path) is str and path and "\0" not in path, "invalid source module path")
        module_hash = digest(module.get("sha256"), "source module digest")
        module_consumed_hash = digest(module.get("source_sha256"), "consumed module digest")
        input_recorded |= path == source_path and module_hash == source_hash and module_consumed_hash == consumed_hash
        changed |= boolean(module.get("changed_since_read"), "module change flag")
    require(input_recorded, "input is absent from the consumed source inventory")
    verification = report.get("verification")
    require(isinstance(verification, dict) and verification.get("requested") is True
            and verification.get("completed") is True, "report lacks completed requested IR verification")
    attempts = report.get("attempts")
    require(isinstance(attempts, list) and len(attempts) <= 128, "invalid attempt inventory")
    normalized = []
    for attempt in attempts:
        require(isinstance(attempt, dict), "invalid attempt")
        pipeline = attempt.get("pipeline")
        require(isinstance(pipeline, dict), "attempt has no pipeline")
        completed = pipeline.get("completed_stages")
        require(isinstance(completed, list) and len(completed) <= 6, "invalid completed stages")
        evidence = pipeline.get("stages")
        require(isinstance(evidence, list) and all(isinstance(item, dict) for item in evidence),
                "invalid pipeline stage evidence")
        require([item.get("name") for item in evidence] == list(STAGES), "invalid pipeline stage inventory")
        active = pipeline.get("active_stage")
        normalized.append({
            "index": natural(attempt.get("index"), "attempt index"),
            "status": choice(attempt.get("status"), ATTEMPT_STATUS, "attempt status"),
            "consistent": choice(pipeline.get("source_provenance"),
                                 {"consistent": True, "inconsistent": False}, "attempt provenance"),
            "complete": choice(pipeline.get("status"), {"completed": True, "partial": False}, "pipeline status"),
            "state": {
                "stage": choice(pipeline.get("stage"), {"new": 0, **STAGE_NUMBERS}, "last completed stage"),
                "active": 0 if active is None else choice(active, STAGE_NUMBERS, "active stage"),
                "history": [choice(stage, STAGE_NUMBERS, "completed stage") for stage in completed],
            },
            "evidence": [choice(item.get("status"), EVIDENCE, "stage evidence") for item in evidence],
        })
    return {"report": {
        "attempts": normalized,
        "report_complete": choice(report.get("status"),
                                  {"ok": True, "error": False, "timeout": False, "rejected": False}, "report status"),
        "source_consistent": not changed,
        "snapshot_complete": choice(snapshot.get("status"), {"completed": True, "partial": False}, "snapshot status"),
        "snapshot_attempt": natural(snapshot.get("attempt"), "snapshot attempt"),
        "target": target,
    }}


def invoke(candidate, checker=DEFAULT_CHECKER):
    payload = json.dumps(candidate, sort_keys=True, separators=(",", ":"))
    require(len(payload.encode()) <= bridge.MAX_BYTES, "pipeline candidate exceeds 4 MiB")
    result = subprocess.run([str(checker)], input=payload, text=True, capture_output=True, timeout=10)
    require(result.returncode in (0, 1), f"Lean checker failed: {result.stderr or result.stdout}")
    output = json.loads(result.stdout, object_pairs_hook=bridge.unique_object)
    require(isinstance(output, dict) and set(output) == {"accepted", "attempts"}, "invalid Lean pipeline response")
    require(type(output["accepted"]) is bool and output["accepted"] == (result.returncode == 0),
            "Lean acceptance and exit status differ")
    require(type(output["attempts"]) is int and output["attempts"] == len(candidate["report"]["attempts"]),
            "Lean attempt count differs")
    return output["accepted"], hashlib.sha256(payload.encode()).hexdigest()


def check(report, snapshot, snapshot_sha256, checker=DEFAULT_CHECKER):
    candidate = normalize(report, snapshot, snapshot_sha256)
    accepted, candidate_hash = invoke(candidate, checker)
    return {"status": "accepted" if accepted else "rejected", "checked": True,
            "scope": "compiler-stage ordering and snapshot association", "candidate_sha256": candidate_hash,
            "attempts": len(candidate["report"]["attempts"]), "target": STAGES[candidate["report"]["target"] - 1],
            "limitations": LIMITATIONS}, 0 if accepted else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, help="defaults to typed-after.json beside the report")
    parser.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    args = parser.parse_args(argv)
    try:
        report, report_hash = bridge.read_snapshot(args.report, bridge.MAX_PROGRAM_BYTES)
        snapshot, snapshot_hash = bridge.read_snapshot(args.snapshot or args.report.parent / "typed-after.json",
                                                      bridge.MAX_PROGRAM_BYTES)
        fields, code = check(report, snapshot, snapshot_hash, args.checker)
        fields.update(report_sha256=report_hash, snapshot_sha256=snapshot_hash)
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as error:
        fields, code = {"status": "error", "checked": False, "error": str(error), "limitations": LIMITATIONS}, 3
    print(json.dumps(fields, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
