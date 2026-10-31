#!/usr/bin/env python3
"""Package fresh validation records without invoking a compiler."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def raw_record(data):
    result = {"bytes": len(data)}
    try:
        result.update(encoding="utf-8", text=data.decode("utf-8"))
        assert result["text"].encode("utf-8") == data
    except UnicodeDecodeError:
        result.update(encoding="base64", data=base64.b64encode(data).decode("ascii"))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-candidate-commit", required=True)
    parser.add_argument("--expected-candidate-tree", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ci", type=Path, default=ROOT.parent / "final-ci/correctness-evidence.json")
    args = parser.parse_args()
    temporary = args.output.with_name(args.output.name + ".tmp")
    assert not args.output.exists() and not temporary.exists(), "Preserve earlier exports; choose a new output path"
    expected = (args.expected_candidate_commit, args.expected_candidate_tree)
    plan = read(ROOT / "plan.json")
    fixtures = read(ROOT / "fixtures/evidence.json")
    run = read(ROOT / "irsame/run.json")
    audit = read(ROOT / "irsame/irsame-audit.json")
    before = read(ROOT / "irsame/sources-before.json")
    after = read(ROOT / "irsame/sources-after.json")
    fixture_before = read(ROOT / "fixtures/sources-before.json")
    fixture_after = read(ROOT / "fixtures/sources-after.json")
    assert (plan["candidate_commit"], plan["candidate_tree"]) == expected
    assert (fixtures["candidate_commit"], fixtures["tree"]) == expected
    assert (run["expected_candidate_commit"], run["expected_candidate_tree"]) == expected
    assert (before["new"]["commit"], before["new"]["tree"]) == expected
    assert before == after and fixture_before == fixture_after == before["new"]
    assert fixtures["status"] == audit["status"] == "passed"
    assert fixtures["source_identity_stable"] and run["source_identity_stable"] and audit["source_identity_stable"]
    assert run["status"] == "captured" and run["harness_exit_status"] in (0, 1)
    assert audit["harness_exit_status_preserved"] == run["harness_exit_status"]
    assert audit["all_retained_ir_archives_rehashed"] and audit["runtime_ir_identical"]
    assert not audit["remaining_review_cases"]
    assert sha(ROOT / "validate.py") == plan["controller_sha256"] == fixtures["controller_sha256"] == run["controller_sha256"]
    assert sha(ROOT / "prepared-corpus.txt") == plan["corpus_sha256"]
    assert sha(ROOT / "irsame-prepared.sh") == plan["instrumented_harness_sha256"]
    assert (ROOT / "irsame/cases/cases.txt").read_bytes() == (ROOT / "prepared-corpus.txt").read_bytes()
    cases = (ROOT / "prepared-corpus.txt").read_text().splitlines()
    assert len(cases) == len(set(cases)) == len(audit["results"]) == plan["corpus_cases"] == 3918

    fixture_results = []
    assert {row["name"] for row in fixtures["results"]} == set(plan["expected_mode_totals"])
    for row in fixtures["results"]:
        assert row["passed"] and row["exit_code"] == 0
        expected_total = plan["expected_mode_totals"][row["name"]]
        assert row["expected_executions"] == expected_total
        assert row["reported_totals"] == [[str(expected_total), "0"]]
        log = ROOT / "fixtures" / (row["name"] + ".log")
        assert sha(log) == row["log_sha256"]
        fixture_results.append({**row, "raw_log": raw_record(log.read_bytes())})
    assert sum(row["expected_executions"] for row in fixture_results) == 150

    bootstraps = {}
    for side, path_key, hash_key in (("candidate", "candidate_build", "candidate_build_sha256"),
                                    ("main", "baseline_build", "baseline_build_sha256")):
        path = Path(run[path_key])
        assert sha(path) == run[hash_key]
        data = read(path)
        assert data["status"] == "complete" and data["exit_code"] == 0 and data["source_identity_stable"]
        assert data["before"] == data["after"]
        identity = before["new" if side == "candidate" else "old"]
        assert (data["commit"], data["tree"]) == (identity["commit"], identity["tree"])
        assert data["artifacts"]["pystachy"]["sha256"] == identity["native_compiler"]["sha256"]
        bootstraps[side] = {"record_path": str(path), "record_sha256": sha(path),
                            "commit": data["commit"], "tree": data["tree"], "source_identity_stable": True,
                            "artifacts": data["artifacts"], "log_sha256": data["log_sha256"],
                            "seconds": data["seconds"], "fresh_after_workspace_cleanup": True}
    assert fixtures["bootstrap_sha256"] == bootstraps["candidate"]["record_sha256"]

    diagnostics, results = {}, []
    for index, (filename, row) in enumerate(zip(cases, audit["results"]), 1):
        assert row["index"] == index and row["file"] == filename and row["complete"]
        assert row["diagnostic_filename_only"]
        assert not row["status_changed"] and not row["new_rejection"] and not row["new_acceptance"]
        assert row["old"]["status"] == row["new"]["status"]
        folder = ROOT / "irsame/cases" / str(index)
        assert (folder / "source.txt").read_bytes() == (filename + "\n").encode()
        assert (folder / "mode.txt").read_bytes() == (row["mode"] + "\n").encode()
        assert (folder / "audit-complete.txt").read_text() == "complete\n"
        result = {**row, "old": dict(row["old"]), "new": dict(row["new"])}
        for side in ("old", "new"):
            data = row[side]
            status = int((folder / (side + ".status")).read_text())
            assert status == data["status"] and status in (0, 1)
            raw = (folder / (side + ".msg")).read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            assert checksum == data["messages_sha256"]
            encoded = raw_record(raw)
            if checksum in diagnostics:
                assert diagnostics[checksum] == encoded
            else:
                diagnostics[checksum] = encoded
            archive = folder / (side + ".ll.gz")
            sidecars = [folder / (side + ".ll.sha256"), folder / (side + ".ll.bytes")]
            presence = [archive.exists(), *[path.exists() for path in sidecars]]
            assert all(presence) or not any(presence)
            assert status != 0 or all(presence)
            if data["ir_sha256"] is None:
                assert not any(presence)
            else:
                assert all(presence)
                assert sidecars[0].read_text().split()[0] == data["ir_sha256"]
                assert int(sidecars[1].read_text()) == data["ir_bytes"]
                assert sha(archive) == data["compressed_sha256"]
                result[side]["compressed_bytes"] = archive.stat().st_size
        results.append(result)

    ci = read(args.ci)
    assert ci["status"] == "passed" and (ci["source"]["head"], ci["source"]["tree"]) == expected
    metadata_files = ["plan.json", "validate.py", "irsame/run.json", "irsame/irsame-audit.json", "irsame/harness.log",
                      "irsame/sources-before.json", "irsame/sources-after.json", "irsame/irsame-original.sh",
                      "irsame/irsame-instrumented.sh", "fixtures/evidence.json", "fixtures/sources-before.json",
                      "fixtures/sources-after.json"]
    metadata = {name: {"sha256": sha(ROOT / name), "bytes": (ROOT / name).stat().st_size} for name in metadata_files}
    output = {
        "schema": "pystachy-recursion-fresh-validation-v1", "status": "passed",
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": {"fresh_after_workspace_cleanup": True, "historical_amd_timing_series_reused": False,
                       "lost_original_local_evidence": "not reconstructed", "host": run["host"],
                       "exporter_sha256": sha(Path(__file__)), "metadata_files": metadata},
        "scope": {
            "compilation": "Full compilation status and diagnostic compatibility with main; intentional LLVM changes retained. This alone does not prove runtime equivalence.",
            "runtime": "Twenty focused fixtures, 150 native JIT/AOT/configuration executions against repository expectations.",
            "ir_archives": "Complete compressed LLVM retained locally. Full raw hashes, sizes and archive hashes are exported; archives are unchanged since the complete decompression audit.",
            "diagnostics": "Every raw diagnostic is present in the SHA256-keyed pool. UTF-8 text round-trips exactly, with base64 fallback; the unchanged audit records every permitted filename substitution."
        },
        "source_identity": {"before": before, "after_equals_before": True,
                            "fixture_candidate_snapshot_equals_comparison_candidate": True},
        "bootstraps": bootstraps,
        "fixtures": {"status": "passed", "fixture_paths": plan["fixtures"], "leaf_disabled_paths": plan["leaf_fixtures"],
                     "executions": 150, "source_identity_stable": True, "results": fixture_results},
        "compilation_comparison": {"status": "passed", "command": run["command"], "jobs": run["jobs"],
                                   "harness_exit_status_preserved": run["harness_exit_status"], "counts": audit["counts"],
                                   "corpus_sha256": plan["corpus_sha256"], "runtime_ir_identical": True,
                                   "filename_mapping": audit["filename_mapping"], "diagnostics": diagnostics, "results": results},
        "ci": {"evidence_sha256": sha(args.ci), "evidence": ci},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output)
    print(json.dumps({"path": str(args.output), "sha256": sha(args.output), "bytes": args.output.stat().st_size,
                      "case_count": len(results), "diagnostic_pool_entries": len(diagnostics),
                      "fixture_executions": 150, "counts": audit["counts"]}, indent=2))


if __name__ == "__main__":
    main()
