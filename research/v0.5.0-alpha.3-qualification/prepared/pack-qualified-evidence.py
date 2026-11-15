"""Preserve completed, reviewed alpha.3 evidence without changing release source."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
INITIAL = ROOT / "research-publish/storage-repair-checkpoint"
OUT = ROOT / "research-publish/qualified"
LEAN = ROOT / "evidence/lean-storage-corrected"
FINAL_SOURCE = "0a2fe77a580106c197face4d2904be80e3f85dbc"
FINAL_TREE = "107460d5f89bdcf37f2741b233eac0568d82604a"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--ci-directory", type=Path, required=True)
args = parser.parse_args()
CI = args.ci_directory.resolve()
CI.relative_to(ROOT / "evidence/ci")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def put(name, data):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())


def copy(source, target):
    put(target, (ROOT / source).read_bytes())


verified_identities = {}


def verify_recorded_identities(value):
    if isinstance(value, list):
        for item in value:
            verify_recorded_identities(item)
    elif isinstance(value, dict):
        if {"path", "bytes", "sha256"}.issubset(value):
            path = Path(value["path"])
            if path.is_absolute():
                key = str(path)
                if key not in verified_identities:
                    data = path.read_bytes()
                    verified_identities[key] = (len(data), digest(data))
                assert verified_identities[key] == (value["bytes"], value["sha256"]), key
        for item in value.values():
            verify_recorded_identities(item)


def require_review(name, status):
    result = json.loads((LEAN / name).read_text())
    assert result["status"] == status, name
    assert result["checks"] and all(value is True for value in result["checks"].values()), name
    verify_recorded_identities(result)
    return result


def bundle(name, paths):
    rows = []
    with (OUT / name).open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in sorted(set(paths), key=lambda p: str(p).encode()):
                    data = path.read_bytes()
                    relative = str(path.relative_to(ROOT))
                    info = tarfile.TarInfo(relative)
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(data))
                    rows.append({"path": relative, "bytes": len(data), "sha256": digest(data)})
    put(name + ".manifest.json.gz", gzip.compress((json.dumps(rows, indent=2) + "\n").encode(), mtime=0))


acceptance = json.loads((LEAN / "acceptance.json").read_text())
assert acceptance["programs"] == 2699 and acceptance["storage_programs"] == 196
assert acceptance["commit"] == FINAL_SOURCE and acceptance["tree"] == FINAL_TREE
required_checks = {
    "exact_corpus_census", "exact_program_count", "exact_storage_census", "exact_storage_count",
    "baseline_program_names_retained", "baseline_storage_program_names_retained",
    "header_inventory_matches", "full_not_selected_inputs", "source_commit_matches",
    "source_tree_matches", "source_clean", "clean_inputs", "input_identities_match",
    "checker_identities_match", "all_copied_checker_hashes_match", "all_checker_sources_match",
    "python_matches", "platform_matches", "completion_matches_records", "completion_valid",
    "no_incomplete_or_failed_records", "valid_numeric_check_records", "strict_storage_all_accepted",
}
assert set(acceptance["checks"]) == required_checks
assert all(value is True for value in acceptance["checks"].values())
assert not acceptance["failed_records"] and not acceptance["incomplete_records"]
assert not acceptance["invalid_records"] and not acceptance["storage_gaps"]
assert digest((LEAN / "records.jsonl").read_bytes()) == acceptance["records_sha256"]
assert digest((LEAN / "report.md").read_bytes()) == acceptance["report_sha256"]
for name in ("semantic-disposition.json", "semantic-disposition.md", "historical-attempt-comparison.json"):
    assert (LEAN / name).is_file(), name
binding = require_review("count-attribution/final-census-binding.json", "bound_to_complete_final_source_census")
assert binding["semantic_approval_granted"] is False
semantics = require_review("semantic-disposition.json", "reviewed_with_explicit_model_limits")
assert semantics["candidate_commit"] == FINAL_SOURCE and semantics["candidate_tree"] == FINAL_TREE
independent = require_review("independent-review/final-acceptance.json", "accepted_with_explicit_model_limits")
assert independent["schema_version"] == 1
assert (LEAN / "independent-review/final-acceptance.md").is_file()
census_receipt = require_review("final-census-receipt.json", "complete_and_strict_storage_accepted")
assert census_receipt["candidate_commit"] == FINAL_SOURCE and census_receipt["candidate_tree"] == FINAL_TREE
readme = (ROOT / "evidence/premerge-qualified-README.md").read_text()
assert readme and all(marker not in readme for marker in
                      ("PLACEHOLDER", "TBD", "__REQUIRED_", "UNFINALIZED TEMPLATE"))
merged_path = ROOT / "evidence/lean/optional-storage-repair/merged-tree-equivalence.json"
merged = json.loads(merged_path.read_text())
assert merged["repair_commit"] == FINAL_SOURCE and merged["release_tree"] == FINAL_TREE
assert merged["identical_tree"] is True
ci = json.loads((CI / "qualification.json").read_text())
assert ci["head"] == merged["release_commit"] and ci["pr_number"] == 1494
assert ci["status"] == "all_observed_runs_completed" and not ci["failures"]
for name in ("CI", "Lint", "Submission format"):
    assert ci["gate_statuses"][name]["status"] == "completed"
    assert ci["gate_statuses"][name]["conclusion"] == "success"
assert ci["gate_statuses"]["CodeQL"]
assert all(row["status"] == "completed" and row["conclusion"] == "success"
           for row in ci["gate_statuses"]["CodeQL"])
prior_receipt = json.loads((ROOT / "evidence/research-publication-storage-checkpoint.json").read_text())
initial_manifest = json.loads((INITIAL / "upload-manifest.json").read_text())
for row in initial_manifest["files"]:
    data = (INITIAL / row["path"]).read_bytes()
    assert len(data) == row["bytes"] and digest(data) == row["sha256"], row["path"]
assert not OUT.exists(), "Freeze one immutable package per publication attempt."
shutil.copytree(INITIAL, OUT)
(OUT / "upload-manifest.json").unlink()
(OUT / "SHA256SUMS").unlink()

copy("evidence/premerge-qualified-README.md", "README.md")
for name in ("report.md", "acceptance.json", "delta-alpha2.json", "semantic-disposition.json",
             "semantic-disposition.md", "historical-attempt-comparison.json", "final-census-receipt.json",
             "count-attribution/final-census-binding.json"):
    copy("evidence/lean-storage-corrected/" + name, "lean-final/" + name)
baseline_path = Path(json.loads((LEAN / "delta-alpha2.json").read_text())["baseline_records"])
baseline_data = baseline_path.read_bytes()
assert digest(baseline_data) == "98d2cd703064e39dbb14e41f3d13bb1b5df7bbcf4d30903966db4b427ecd09a6"
put("lean-final/alpha2-baseline-records.jsonl.gz", gzip.compress(baseline_data, mtime=0))
put("lean-final/alpha2-baseline-records-identity.json", json.dumps({
    "source_path": str(baseline_path), "uncompressed_bytes": len(baseline_data),
    "uncompressed_sha256": digest(baseline_data),
    "source_commit": "950c0440ad793dc6c34664f591383a5e6bba14dd",
    "published_alpha2_commit": "80490143498d149d407343ba1cb7aedb1db2d2c5",
    "equivalent_tree": "717a8c9386ae9f5f6545cc3686a9e22282fc560c"}, indent=2) + "\n")
for path in (LEAN / "independent-review").glob("*"):
    if path.is_file() and path.suffix in (".json", ".md"):
        copy(str(path.relative_to(ROOT)), "lean-final/independent-review/" + path.name)
for name in ("full-disposition.md", "accepted-ir-review.md", "tomllib-guard-attribution-correction.md"):
    copy("evidence/ir-review/" + name, "ir/" + name)
for name in ("qualification.json", "qualification.md"):
    copy(str((CI / name).relative_to(ROOT)), "integrated-final-pr-checks." + name.rsplit(".", 1)[1])
repair_ci = json.loads((ROOT / "evidence/ci/pr1501/qualification.json").read_text())
assert repair_ci["head"] == FINAL_SOURCE and repair_ci["status"] == "all_observed_runs_completed"
assert not repair_ci["failures"]
for name in ("qualification.json", "qualification.md"):
    copy("evidence/ci/pr1501/" + name, "repair-final-pr-checks." + name.rsplit(".", 1)[1])

excluded = []
lean_paths = []
for path in LEAN.rglob("*"):
    if not path.is_file() or "__pycache__" in path.parts:
        continue
    if path.name in {"typed-after.json", "typed-before.json"} or path.suffix in {".ll", ".bc"}:
        data = path.read_bytes()
        excluded.append({"path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": digest(data),
                         "reason": "Reproducible full compiler snapshot; exact extracted sites, commands, module identities and hashes are retained."})
    else:
        lean_paths.append(path)
put("lean-final/excluded-reproducible-snapshots.json", json.dumps(excluded, indent=2) + "\n")
lean_paths += [p for p in (ROOT / "evidence/lean/tomllib-count-attribution-support").rglob("*") if p.is_file()]
lean_paths += [p for p in (ROOT / "evidence/lean/vtuple-count-attribution-support").rglob("*") if p.is_file()]
bundle("lean-final-full-census.tar.gz", lean_paths)

ci_paths = [p for p in (ROOT / "evidence/ci").rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".zip", ".gz"}]
bundle("premerge-workflow-evidence.tar.gz", ci_paths)
copy(str(merged_path.relative_to(ROOT)), "final-merged-tree-equivalence.json")
copy("evidence/research-publication-storage-checkpoint.json", "prior-research-checkpoint.json")
copy("qualification-tools/pack-qualified-evidence.py", "pack-qualified-evidence.py")
copy("qualification-tools/finalize-qualified-readme.py", "tools/finalize-qualified-readme.py")
copy("evidence/premerge-qualified-README.template.md", "tools/premerge-qualified-README.template.md")

files = []
for path in sorted(OUT.rglob("*")):
    if path.is_file():
        data = path.read_bytes()
        files.append({"path": str(path.relative_to(OUT)), "bytes": len(data), "sha256": digest(data),
                      "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
put("SHA256SUMS", "".join(f"{row['sha256']}  {row['path']}\n" for row in files))
checksum = (OUT / "SHA256SUMS").read_bytes()
files.append({"path": "SHA256SUMS", "bytes": len(checksum), "sha256": digest(checksum),
              "git_blob": hashlib.sha1(b"blob " + str(len(checksum)).encode() + b"\0" + checksum).hexdigest()})
prior = {row["path"]: row["git_blob"] for row in initial_manifest["files"]}
changed = [row for row in files if prior.get(row["path"]) != row["git_blob"]]
put("upload-manifest.json", json.dumps({"created_utc": datetime.now(timezone.utc).isoformat(),
                                       "root": str(OUT), "files": files, "changed": changed,
                                       "expected_research_head": prior_receipt["commit"],
                                       "expected_research_tree": prior_receipt["tree"]}, indent=2) + "\n")
print(json.dumps({"root": str(OUT), "files": len(files), "changed_files": len(changed),
                  "changed_bytes": sum(row["bytes"] for row in changed),
                  "excluded_snapshots": len(excluded)}, indent=2))
