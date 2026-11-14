"""Package the complete retained audit without unchanged LLVM IR files."""
from collections import Counter
import hashlib
import json
import lzma
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "publication"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    data = json.loads((ROOT / "classification.json").read_text())
    assert data["completed"] == data["total_comparisons"] == 4650
    assert data["pending"] == 0
    assert set(data["counts"]) == {"unchanged", "library-path-only difference", "improved acceptance",
                                  "meaningful IR change", "reviewed installation-path-only difference"}
    identities = {key: json.loads((ROOT / (key + "-identity.json")).read_text()) for key in ("old", "new")}
    mapping = json.loads((ROOT.parent / "publication-map.json").read_text())
    public = {row["local"]: row for row in mapping["commits"]}
    assert identities["new"]["source_tree"] == public[identities["new"]["source_ref"]]["tree"] == "30d991ebec23d92140381b4cd6fe6892a31b5a2b"
    assert public[identities["new"]["source_ref"]]["remote"] == "adf5a12a147649d01018dd49c8167610812ada00"
    source_check = json.loads((ROOT / "source-rechecked.json").read_text())
    assert source_check["before_and_after_inputs_identical"]
    oracle = json.loads((ROOT / "oracle.json").read_text())
    assert sha(ROOT / "retaining-irsame.sh") == oracle["wrapper_sha256"] == source_check["wrapper_sha256"]
    for key in identities:
        assert sha(ROOT / (key + "-identity.json")) == source_check[key + "_identity_sha256"]
    summary = {key: value for key, value in data.items() if key != "results"}
    summary["status_counts"] = [{"old": old, "new": new, "count": count}
                                for (old, new), count in sorted(Counter((r["old_status"], r["new_status"])
                                                                      for r in data["results"]).items())]
    summary["raw_oracle_difference_count"] = sum(bool(row["oracle_report"]) for row in data["results"])
    summary["raw_oracle_exit"] = int((ROOT / "raw.status").read_text())
    summary["canonical_test_counts"] = {key: record["canonical_count"] for key, record in identities.items()}
    summary["source_file_counts"] = {key: len(record["source_files"]) for key, record in identities.items()}
    summary["identities"] = {key: {k: v for k, v in record.items() if k not in ("source_files", "cases")}
                             for key, record in identities.items()}
    summary["public_candidate_commit"] = "adf5a12a147649d01018dd49c8167610812ada00"
    summary["public_candidate_tree"] = "30d991ebec23d92140381b4cd6fe6892a31b5a2b"
    summary["public_compiled_source_commit"] = "adf5a12a147649d01018dd49c8167610812ada00"
    summary["checkpoint_status"] = "final source audit, including owned optional-integer delegation cleanup"
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with lzma.open(OUT / "source-identities.json.xz", "wt", preset=6) as stream:
        json.dump(identities, stream, indent=2)
        stream.write("\n")
    with (OUT / "case-results.jsonl").open("w") as stream:
        for row in data["results"]:
            directory = Path(row["directory"])
            record = dict(row)
            record["mode"] = (directory / "mode").read_text().strip()
            record["search_path"] = (directory / "search-path").read_text().strip()
            for side in ("old", "new"):
                message = (directory / (side + ".msg")).read_bytes()
                record[side + "_message_sha256"] = hashlib.sha256(message).hexdigest()
                normal = directory / (side + ".normal.msg")
                record[side + "_normalized_message"] = normal.read_text() if normal.exists() else message.decode()
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
    for name in ("inventory.json", "source-rechecked.json", "oracle.json", "command.json",
                 "raw.log", "raw.status", "times.txt", "old-cases.txt", "new-cases.txt",
                 "meaningful-ir-functions.json", "run-script.sha256"):
        shutil.copy2(ROOT / name, OUT / name)
    shutil.copy2(ROOT.parent / "publication-map.json", OUT / "publication-map.json")
    for source, target in (("manifest.json", "final-bootstrap-manifest.json"),
                           ("inputs.json", "final-bootstrap-inputs.json"),
                           ("bootstrap.log", "final-bootstrap.log")):
        shutil.copy2(ROOT.parent / "final-bootstrap" / source, OUT / target)
    baseline_manifest = Path(identities["old"]["evidence"]["manifest"])
    shutil.copy2(baseline_manifest, OUT / "baseline-bootstrap-manifest.json")
    (OUT / "scripts").mkdir()
    for name in ("prepare.py", "run.py", "classify.py", "retaining-irsame.sh", "package.py", "explain_ir.py", "write_readme.py"):
        shutil.copy2(ROOT / name, OUT / "scripts" / name)

    raw_manifest = {}
    def portable_header(info):
        info.uid = info.gid = info.mtime = 0
        info.uname = info.gname = ""
        info.mode = 0o644
        return info

    changed = [row for row in data["results"] if row["oracle_report"]]
    with tarfile.open(OUT / "raw-changed-cases.tar.xz", "w:xz", preset=6) as archive:
        for number, row in enumerate(changed, 1):
            directory = Path(row["directory"])
            for path in sorted(directory.rglob("*")):
                if not path.is_file():
                    continue
                name = f"raw/{row['index']}/{path.relative_to(directory)}"
                raw_manifest[name] = {"sha256": sha(path), "bytes": path.stat().st_size}
                archive.add(path, arcname=name, recursive=False, filter=portable_header)
            if number % 25 == 0:
                print(f"Packed {number}/{len(changed)} changed cases", flush=True)
    (OUT / "raw-files.json").write_text(json.dumps(raw_manifest, indent=2) + "\n")
    print(json.dumps({"publication": str(OUT), "raw_archive_bytes": (OUT / "raw-changed-cases.tar.xz").stat().st_size,
                      "raw_files": len(raw_manifest), "raw_input_bytes": sum(v["bytes"] for v in raw_manifest.values())}, indent=2), flush=True)


if __name__ == "__main__":
    main()
