"""Freeze an explicitly incomplete census prefix and completed supporting evidence.

Never invokes the compiler, a checker, a finalizer, GitHub, or the live runner.
The active record file is read once to its size at open; only complete lines are
retained. Large typed snapshots are never opened. Existing files are read only.
"""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tarfile


ROOT = Path(__file__).resolve().parents[1]
INITIAL = ROOT / "research-publish/storage-repair-checkpoint"
OUT = ROOT / "research-publish/final-census-progress"
LEAN = ROOT / "evidence/lean-storage-corrected"
SOURCE = "0a2fe77a580106c197face4d2904be80e3f85dbc"
TREE = "107460d5f89bdcf37f2741b233eac0568d82604a"
MERGED = "328b945f02788b296d9981d1b44706a2a0092255"
LEASE = "788ede51e18a11ece70c38bd0c5152b6a01a197b"
LEASE_TREE = "0ce7be22915a6ad99cb509cb3cfac219b1894600"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stable_read(path):
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_ino, after.st_size, after.st_mtime_ns), path
    assert len(data) == before.st_size
    return data


def put(name, data):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data if isinstance(data, bytes) else data.encode())


def put_json(name, data):
    put(name, json.dumps(data, indent=2) + "\n")


def copy(source, target):
    put(target, stable_read(ROOT / source))


def files(directory):
    return [p for p in directory.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts]


def file_identity(path):
    data = stable_read(path)
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": digest(data)}


def bundle(name, paths):
    members = []
    with (OUT / name).open("xb") as output:
        with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0, compresslevel=6) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in sorted(set(paths), key=lambda p: str(p).encode()):
                    assert path.name not in {"typed-after.json", "typed-before.json"}
                    assert path.suffix not in {".ll", ".bc"}
                    data = stable_read(path)
                    relative = str(path.relative_to(ROOT))
                    info = tarfile.TarInfo(relative)
                    info.size, info.mode, info.mtime = len(data), 0o644, 0
                    info.uid, info.gid, info.uname, info.gname = 0, 0, "", ""
                    archive.addfile(info, io.BytesIO(data))
                    members.append({"path": relative, "bytes": len(data), "sha256": digest(data)})
    manifest = (json.dumps(members, indent=2) + "\n").encode()
    put(name + ".manifest.json.gz", gzip.compress(manifest, mtime=0))
    # Read the new archive, not the original inputs, for a complete member check.
    with tarfile.open(OUT / name, "r:gz") as archive:
        actual = archive.getmembers()
        assert [m.name for m in actual] == [m["path"] for m in members]
        for entry, expected in zip(actual, members, strict=True):
            assert entry.isfile() and entry.mode == 0o644 and entry.mtime == 0
            assert entry.uid == entry.gid == 0 and entry.uname == entry.gname == ""
            stream = archive.extractfile(entry)
            assert stream is not None
            assert entry.size == expected["bytes"]
            assert hashlib.file_digest(stream, "sha256").hexdigest() == expected["sha256"]
    return {"archive": name, "members": len(members),
            "uncompressed_member_bytes": sum(row["bytes"] for row in members),
            "archive_bytes": (OUT / name).stat().st_size,
            "archive_sha256": digest((OUT / name).read_bytes()),
            "member_manifest": name + ".manifest.json.gz",
            "all_member_identities_verified": True,
            "deterministic_metadata": "sorted paths; tar mtime/uid/gid zero, mode0644; gzip mtime0 and empty filename"}


assert not OUT.exists(), "Never overwrite a checkpoint."
started = now()
prior_receipt_path = ROOT / "evidence/research-publication-storage-checkpoint.json"
prior_receipt = json.loads(stable_read(prior_receipt_path))
assert (prior_receipt["commit"], prior_receipt["tree"]) == (LEASE, LEASE_TREE)
initial_manifest = json.loads(stable_read(INITIAL / "upload-manifest.json"))
for row in initial_manifest["files"]:
    data = stable_read(INITIAL / row["path"])
    assert (len(data), digest(data)) == (row["bytes"], row["sha256"]), row["path"]
shutil.copytree(INITIAL, OUT)
# Move only the newly copied manifests/README; the original checkpoint is untouched.
(OUT / "history").mkdir()
(OUT / "README.md").rename(OUT / "storage-repair-checkpoint-README.md")
(OUT / "upload-manifest.json").rename(OUT / "history/storage-repair-checkpoint-upload-manifest.json")
(OUT / "SHA256SUMS").rename(OUT / "history/storage-repair-checkpoint-SHA256SUMS")
copy("evidence/research-publication-storage-checkpoint.json", "prior-research-checkpoint.json")

prepared_data = stable_read(LEAN / "prepared.json")
prepared = json.loads(prepared_data)
assert (prepared["commit"], prepared["tree"]) == (SOURCE, TREE)
assert (prepared["expected_programs"], prepared["expected_promoting"]) == (2699, 196)
record_path = LEAN / "records.jsonl"
capture_started = now()
with record_path.open("rb") as stream:
    before = os.fstat(stream.fileno())
    captured = stream.read(before.st_size)  # Sole read of the active record bytes.
    after = os.fstat(stream.fileno())
capture_finished = now()
assert len(captured) == before.st_size and before.st_ino == after.st_ino
assert after.st_size >= before.st_size, "Live record file unexpectedly shrank."
last_newline = captured.rfind(b"\n")
assert last_newline >= 0
prefix, tail = captured[:last_newline + 1], captured[last_newline + 1:]
lines = prefix.splitlines()
header = json.loads(lines[0])["header"]
assert SOURCE.startswith(header["commit"])
assert header["inputs"] == prepared["inputs"]
assert header["checker_executables"] == prepared["checker_executables"]
assert header["promoting"] == prepared["promoting"]
programs = [json.loads(line)["program"] for line in lines[1:]]
assert all(program in prepared["programs"] for program in programs)
assert len(programs) <= prepared["expected_programs"]
capture = {
    "status": "INCOMPLETE_PROGRESS_SNAPSHOT_NOT_FINAL_ACCEPTANCE",
    "source_path": str(record_path), "source_commit": SOURCE, "source_tree": TREE,
    "capture_started_utc": capture_started, "capture_finished_utc": capture_finished,
    "method": "One bounded read to the active append-only file size at open; no live-file rewriting or second read.",
    "source_stat_before": {"device": before.st_dev, "inode": before.st_ino,
                           "bytes": before.st_size, "mtime_ns": before.st_mtime_ns},
    "source_stat_after": {"device": after.st_dev, "inode": after.st_ino,
                          "bytes": after.st_size, "mtime_ns": after.st_mtime_ns},
    "captured_read_bytes": len(captured), "captured_read_sha256": digest(captured),
    "retained_complete_line_bytes": len(prefix), "retained_complete_line_sha256": digest(prefix),
    "complete_lines_including_header": len(lines), "program_record_lines": len(programs),
    "unique_programs": len(set(programs)), "duplicate_program_records": len(programs)-len(set(programs)),
    "expected_programs": 2699, "expected_storage_selections": 196,
    "observed_selected_storage_programs": len(set(programs) & set(header["promoting"])),
    "last_retained_program": programs[-1] if programs else None,
    "excluded_partial_tail_bytes": len(tail),
    "excluded_partial_tail_sha256": digest(tail) if tail else None,
    "excluded_partial_tail_contents_retained": False,
    "header_commit": header["commit"], "header_inputs_match_preparation": True,
    "header_checker_identities_match_preparation": True,
    "header_storage_selection_matches_preparation": True,
    "final_completion_or_acceptance_inferred": False,
    "limitation": "Prefix completeness does not establish census completion, strict-storage acceptance, semantic disposition or final independent review. Later appended bytes are not represented."
}
put("lean-progress/records.complete-prefix.jsonl.gz", gzip.compress(prefix, mtime=0))
put_json("lean-progress/records-prefix-identity.json", capture)
put("lean-progress/prepared.json", prepared_data)
copy("evidence/lean-storage-corrected/run-20261115T075504Z.json", "lean-progress/run-attempt.snapshot.json")

inventory_path = LEAN / "count-attribution/inventory.json"
inventory_data = stable_read(inventory_path)
inventory = json.loads(inventory_data)
assert inventory["all_extractions_completed"] is True
assert inventory["all_baseline_snapshot_inventories_match_census"] is True
assert not inventory["candidate_reference_count_changes"]
assert digest(inventory_data) == "7200136d2f198e297688a66aeceb60eb1e7ade0423e8f2dd27a286fb098ccb00"
snapshot_identities = {}
for row in inventory["rows"]:
    for side, data in row["sides"].items():
        value = data["snapshot"]
        snapshot_identities[Path(value["path"])] = dict(value, side=side, program=row["program"])

support_roots = [LEAN / "count-attribution", LEAN / "independent-review",
                 LEAN / "storage-denominator-review",
                 ROOT / "evidence/lean/tomllib-count-attribution-support",
                 ROOT / "evidence/lean/vtuple-count-attribution-support"]
selected = [p for directory in support_roots for p in files(directory)]
selected += [p for p in LEAN.iterdir() if p.is_file() and
             (p.suffix == ".py" or p.name in {"attribution-config.json", "qualification-script-identities.json",
                                            "qualification-source-equivalence.json", "prepared.json", "attribution-run.log"})]
selected += [ROOT / "qualification-tools" / name for name in
             ("pack-qualified-evidence.py", "finalize-qualified-readme.py", "pack-final-census-progress.py")]
selected += [ROOT / "evidence/premerge-qualified-README.template.md"]
excluded, included = [], []
for path in sorted(set(selected), key=lambda p: str(p).encode()):
    if path.name in {"typed-after.json", "typed-before.json"}:
        recorded = snapshot_identities[path]
        assert path.stat().st_size == recorded["bytes"]
        excluded.append({**recorded, "path": str(path.relative_to(ROOT)),
                         "identity_basis": "Recorded completed attribution snapshot identity; only current file size observed, no payload read or rehash.",
                         "payload_read_during_packaging": False})
    elif path.suffix in {".ll", ".bc"}:
        before = path.stat()
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        after = path.stat()
        assert (before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino)
        excluded.append({"path": str(path.relative_to(ROOT)), "bytes": before.st_size, "sha256": checksum,
                         "identity_basis": "Lightweight streaming hash of excluded LLVM file; no compiler/checker execution.",
                         "payload_read_during_packaging": True})
    else:
        assert path.name not in {"final-acceptance.json", "final-census-binding.json", "semantic-disposition.json"}
        included.append(path)
put_json("lean-progress/excluded-reproducible-files.json", {
    "reason": "Reproducible full typed snapshots and LLVM files are omitted; exact site excerpts, commands, input/module identities and hashes are retained.",
    "typed_snapshots_opened_or_rehashed": False,
    "snapshot_identity_source": file_identity(inventory_path), "files": excluded})
attribution_bundle = bundle("completed-attribution-and-prepared-finalization.tar.gz", included)

ci_root = ROOT / "evidence/ci/pr1494-storage"
ci = json.loads(stable_read(ci_root / "qualification.json"))
frozen_ci = json.loads(stable_read(ci_root / "frozen-final.json"))
repair_ci = json.loads(stable_read(ROOT / "evidence/ci/pr1501/qualification.json"))
assert ci["head"] == MERGED and ci["status"] == "all_observed_runs_completed" and not ci["failures"]
assert frozen_ci["head_sha"] == MERGED and frozen_ci["all_required_observed_workflows_succeeded"] is True
assert repair_ci["head"] == SOURCE and repair_ci["status"] == "all_observed_runs_completed" and not repair_ci["failures"]
for record in frozen_ci["evidence_files"]:
    data = stable_read(Path(record["path"]))
    assert (len(data), digest(data)) == (record["bytes"], record["sha256"])
for scan_name in ("progress-sensitive-data-scan.json", "progress-credential-assignment-scan.json"):
    scan_path = ROOT / "evidence/publication" / scan_name
    scan = json.loads(stable_read(scan_path))
    assert scan["status"] == "no_sensitive_matches_detected" and not scan["matches"]
    for record in scan["files"]:
        data = stable_read(ROOT / record["path"])
        assert (len(data), digest(data)) == (record["bytes"], record["sha256"])
    copy(str(scan_path.relative_to(ROOT)), "publication-scan/" + scan_name)
ci_paths = files(ci_root) + files(ROOT / "evidence/ci/pr1501")
ci_paths = [p for p in ci_paths if p.suffix not in {".zip", ".gz", ".ll", ".bc"}]
ci_bundle = bundle("workflow-evidence-through-328b.tar.gz", ci_paths)
for suffix in ("json", "md"):
    copy(f"evidence/ci/pr1494-storage/qualification.{suffix}", f"integrated-final-pr-checks.{suffix}")
    copy(f"evidence/ci/pr1501/qualification.{suffix}", f"repair-final-pr-checks.{suffix}")
copy("evidence/ci/pr1494-storage/frozen-final.json", "integrated-final-pr-frozen.json")
copy("evidence/lean/optional-storage-repair/merged-tree-equivalence.json", "final-merged-tree-equivalence.json")
copy("qualification-tools/pack-qualified-evidence.py", "prepared/pack-qualified-evidence.py")
copy("qualification-tools/finalize-qualified-readme.py", "prepared/finalize-qualified-readme.py")
copy("evidence/premerge-qualified-README.template.md", "prepared/premerge-qualified-README.template.md")
copy("qualification-tools/pack-final-census-progress.py", "pack-final-census-progress.py")

progress = {
    "schema_version": 1, "status": "INCOMPLETE_PROGRESS_CHECKPOINT",
    "capture_started_utc": started, "packaged_utc": now(),
    "source_commit": SOURCE, "source_tree": TREE, "merged_release_commit": MERGED,
    "base_research_head": LEASE, "base_research_tree": LEASE_TREE,
    "records": capture,
    "completed_attribution": {"programs": len(inventory["rows"]),
                              "side_inspections": len(snapshot_identities),
                              "inventory": file_identity(inventory_path),
                              "final_census_binding": "pending; no binding executed by this package"},
    "archives": [attribution_bundle, ci_bundle],
    "excluded_files": len(excluded), "excluded_bytes": sum(x["bytes"] for x in excluded),
    "excluded_typed_snapshot_bytes_not_read": sum(x["bytes"] for x in excluded if not x["payload_read_during_packaging"]),
    "finalization_scripts_status": "Prepared and preserved only; no finalizer, pack-qualified script or acceptance checker executed by this packager.",
    "final_qualification_pass_claimed": False, "alpha3_publication_verified": False,
    "new_ci_log_sensitive_data_scan": "39 unchanged files: no signed-URL or credential-value candidates detected; both bounded pattern-scan receipts are preserved under publication-scan/.",
    "pending_gates": ["complete final-source census and strict-storage audit",
                      "bind all attribution inventories to final census",
                      "complete semantic disposition and final independent review",
                      "expected-head release merge and all seven exact-main workflows",
                      "native, Docker and PyPI publication with actual public-byte verification"],
    "historical_evidence": "All prior checkpoint files remain preserved; original README, checksum list and upload manifest are retained under explicit historical names.",
    "mutations": "Only this new checkpoint directory and its new packager are created; no prior evidence, live records, source or run is modified."
}
put_json("progress.json", progress)
put("progress.md", f"""# INCOMPLETE final-source census checkpoint

This is a mid-run preservation checkpoint, **not final qualification or release acceptance**. The source is `{SOURCE}` (tree `{TREE}`). The release branch's `{MERGED}` merge has the same tree; this does not change the census execution identity. Research-branch root code is historical; pinned commits identify the qualified inputs.

The one-time capture at {capture_finished} retained **{len(programs):,} complete program record lines of 2,699 expected**, plus the original header. It contains {capture['observed_selected_storage_programs']} of 196 selected storage programs. {len(tail)} partial trailing bytes were excluded. The complete-line prefix SHA256 is `{digest(prefix)}`. No proof totals or final acceptance are inferred from that prefix. [Capture identity](lean-progress/records-prefix-identity.json), [compressed records](lean-progress/records.complete-prefix.jsonl.gz).

Completed attribution covers {len(inventory['rows'])} programs and {len(snapshot_identities)} side inspections. Its inventories, exact site excerpts, reports, independent reviews and prepared finalization scripts are preserved in [the attribution archive](completed-attribution-and-prepared-finalization.tar.gz), with a [member manifest](completed-attribution-and-prepared-finalization.tar.gz.manifest.json.gz). Final-census binding, final semantic disposition and final independent acceptance remain pending. Prepared scripts and the unfinalized README template are inputs, not successful executions.

The [integrated PR checks](integrated-final-pr-checks.md) and [repair PR checks](repair-final-pr-checks.md) are complete on their pinned commits. [Frozen CI identity](integrated-final-pr-frozen.json), [workflow archive](workflow-evidence-through-328b.tar.gz), [member manifest](workflow-evidence-through-328b.tar.gz.manifest.json.gz), [merged-tree identity](final-merged-tree-equivalence.json). These results do not replace remaining proof, expected-head merge, exact-main or publication gates. Automated Codex quota failures remain distinct from completed agent reviews.

The [prior checkpoint README](storage-repair-checkpoint-README.md) and its archives preserve b0 executions, the complete 94f4 strict-storage failure, repair intermediates and all earlier histories. The **542 union / 409 payload residuals, three added GC-gap instances and Decimal unknown-count limitation** remain explicit historical limits requiring final reconciliation; they are not silently converted into proof passes.

Large typed snapshots and LLVM files are [excluded with identities](lean-progress/excluded-reproducible-files.json). Packaging did not read or rehash {progress['excluded_typed_snapshot_bytes_not_read']:,} bytes of typed snapshots. Their existing recorded hashes and reproduction commands are retained. Excluded LLVM identities were obtained by lightweight streaming hashes; no compiler/checker or runtime job was run. The files themselves remain untouched locally.

This package extends research lease `{LEASE}` / tree `{LEASE_TREE}`. [Progress details](progress.json) describe remaining gates; [SHA256SUMS](SHA256SUMS) identifies every payload, and the separate upload manifest identifies that checksum file. Root owns upload/ref updates. Nothing here verifies alpha.3 public artifacts.
""")
put("README.md", """# v0.5.0-alpha.3 — INCOMPLETE progress checkpoint

**Final-source qualification is still incomplete. No final acceptance or alpha.3 publication is claimed.**

Read the [current progress and remaining gates](progress.md), [machine-readable snapshot](progress.json), and [one-time records-prefix identity](lean-progress/records-prefix-identity.json). The completed CI and attribution evidence is preserved alongside the ongoing census prefix; neither substitutes for the pending complete census, binding and independent final review.

The research branch's root code is historical. Source and execution identities come from the pinned commits in those records. The [prior storage-repair checkpoint README](storage-repair-checkpoint-README.md) is preserved verbatim, with its original archives and historical failed/incomplete attempts.

The [checksum list](SHA256SUMS) covers this checkpoint's payloads. The upload manifest records the checksum-list identity without a self-referential README or manifest hash. Archive member manifests retain exact lengths and SHA256 values. Root owns the later publication of this evidence checkpoint; it is not a release artifact or approval.
""")

manifest = []
for path in sorted(files(OUT), key=lambda p: str(p).encode()):
    data = stable_read(path)
    manifest.append({"path": str(path.relative_to(OUT)), "bytes": len(data), "sha256": digest(data),
                     "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
put("SHA256SUMS", "".join(f"{row['sha256']}  {row['path']}\n" for row in manifest))
data = (OUT / "SHA256SUMS").read_bytes()
manifest.append({"path": "SHA256SUMS", "bytes": len(data), "sha256": digest(data),
                 "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
prior = {row["path"]: row["git_blob"] for row in initial_manifest["files"]}
changed = [row for row in manifest if prior.get(row["path"]) != row["git_blob"]]
put_json("upload-manifest.json", {
    "created_utc": now(), "root": str(OUT), "status": "INCOMPLETE_PROGRESS_CHECKPOINT",
    "files": manifest, "changed": changed,
    "expected_research_head": LEASE, "expected_research_tree": LEASE_TREE,
    "manifest_convention": "Payloads are listed in SHA256SUMS; upload-manifest includes SHA256SUMS but excludes itself, matching the prior packer."
})
print(json.dumps({"root": str(OUT), "status": "INCOMPLETE_PROGRESS_CHECKPOINT",
                  "files": len(manifest), "changed_files": len(changed),
                  "file_bytes": sum(row["bytes"] for row in manifest),
                  "changed_bytes": sum(row["bytes"] for row in changed),
                  "program_records_captured": len(programs), "partial_tail_bytes_excluded": len(tail),
                  "attribution_archive": attribution_bundle, "ci_archive": ci_bundle,
                  "excluded_typed_snapshot_bytes_not_read": progress["excluded_typed_snapshot_bytes_not_read"],
                  "upload_manifest_sha256": digest((OUT / "upload-manifest.json").read_bytes()),
                  "checksum_file_sha256": digest((OUT / "SHA256SUMS").read_bytes())}, indent=2))
