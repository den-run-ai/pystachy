"""Build a compact reproducible audit publication set, retaining raw results."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent
PUBLISH = ROOT / "publish"
PUBLISH.mkdir(exist_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_archive():
    summary = json.loads((ROOT / "summary.json").read_text())
    files = []
    allowed = {"case", "mode", "search-path", "source.sha256", "old.status", "new.status",
               "old.msg", "new.msg", "old.normal.msg", "new.normal.msg", "old.msg.sha256", "new.msg.sha256",
               "old.ir.sha256", "new.ir.sha256", "old.ir.bytes", "new.ir.bytes", "report", "old.ll", "new.ll",
               "messages.raw.diff", "ir.raw.diff", "ir.location-normalized.diff", "constructor.residual.diff"}
    for row in summary["cases"]:
        directory = ROOT / row["directory"]
        files.extend(p for p in sorted(directory.iterdir()) if p.is_file() and p.name in allowed)
    manifest = {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in files}
    (ROOT / "raw-files.json").write_text(json.dumps(manifest, separators=(",", ":")) + "\n")
    archive = PUBLISH / "raw-results.tar.xz"
    with archive.open("wb") as output:
        compressor = subprocess.Popen(["xz", "-T2", "-6", "-c"], stdin=subprocess.PIPE, stdout=output)
        with tarfile.open(fileobj=compressor.stdin, mode="w|", format=tarfile.PAX_FORMAT) as tar:
            for path in files:
                info = tar.gettarinfo(path, str(path.relative_to(ROOT)))
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with path.open("rb") as data:
                    tar.addfile(info, data)
        compressor.stdin.close()
        assert compressor.wait() == 0
    print(json.dumps({"raw_archive": str(archive), "files": len(files),
                      "raw_bytes": sum(x["bytes"] for x in manifest.values()),
                      "compressed_bytes": archive.stat().st_size, "sha256": sha(archive)}, indent=2), flush=True)


def finish():
    required = ["prepare.py", "run.py", "inspect.py", "package.py", "constructor_review.py", "final_tree.py", "toolchain.py", "write_readme.py", "triage.py", "reuse_reviews.py",
                "classify_constructors.py", "classify.py", "compare_previous.py", "retaining-irsame.sh", "old-identity.json", "new-identity.json",
                "inventory.json", "old-cases.txt", "new-cases.txt", "command.json", "oracle.json", "toolchain.json",
                "raw.log", "raw.status", "times.txt", "source-rechecked.json", "summary.json", "summary.jsonl", "final-ledger.jsonl",
                "classification.json", "classification.md", "constructor-semantic-review.json", "constructor-mechanical.json",
                "numeric-semantic-review.json", "numeric-review-qualification.json", "comparison-previous.json", "final-tree.json", "final-tools.patch",
                "triage.json", "constructor-review-cases.json", "numeric-review-cases.json",
                "unchanged-home-payloads.json", "raw-files.json", "README.md"]
    paths = {}
    for name in required:
        assert (ROOT / name).is_file(), name
        paths[name] = ROOT / name
    if (ROOT / "overlay").exists():
        for path in (ROOT / "overlay").rglob("*"):
            if path.is_file():
                paths[str(path.relative_to(ROOT))] = path
    if (ROOT / "final-tools").exists():
        for path in (ROOT / "final-tools").rglob("*"):
            if path.is_file():
                paths[str(path.relative_to(ROOT))] = path
    paths["alpha2-baseline-manifest.json"] = ROOT.parent / "alpha2-baseline-manifest.json"
    for name, path in (("candidate-bootstrap.log", Path(json.loads((ROOT / "new-identity.json").read_text())["evidence"]["bootstrap_log"])),
                       ("baseline-bootstrap.log", Path(json.loads((ROOT.parent / "alpha2-baseline-manifest.json").read_text())["bootstrap_log"]))):
        paths[name] = path
    paths["original-irsame.sh"] = ROOT / "home-new/tools/irsame.sh"
    # Keep the readable narrative and replay harness as text; compress the complete
    # large source manifests, per-case ledgers and raw-file hashes without dropping rows.
    plain = {"README.md", "classification.md", "prepare.py", "run.py", "inspect.py", "classify.py", "compare_previous.py", "final_tree.py", "toolchain.py", "write_readme.py", "triage.py", "reuse_reviews.py",
             "constructor_review.py", "classify_constructors.py", "package.py", "retaining-irsame.sh", "original-irsame.sh"}
    for name in plain:
        shutil.copy2(paths[name], PUBLISH / name)
    metadata = {name: {"sha256": sha(path), "bytes": path.stat().st_size} for name, path in paths.items()}
    (ROOT / "metadata-files.json").write_text(json.dumps(metadata, indent=2) + "\n")
    paths["metadata-files.json"] = ROOT / "metadata-files.json"
    with tarfile.open(PUBLISH / "manifests-and-ledgers.tar.xz", "w:xz", preset=6) as tar:
        for name, path in sorted(paths.items()):
            info = tar.gettarinfo(path, name)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with path.open("rb") as data:
                tar.addfile(info, data)
    files = {str(path.relative_to(PUBLISH)): {"sha256": sha(path), "bytes": path.stat().st_size}
             for path in sorted(PUBLISH.rglob("*")) if path.is_file() and path.name != "bundle-manifest.json"}
    manifest = {"files": files, "total_bytes": sum(row["bytes"] for row in files.values()),
                "purpose": "Pinned full native IR audit; complete source manifests, per-case ledgers, raw-file hashes and every changed IR are retained. Cross-audit review reuse is recorded explicitly."}
    (PUBLISH / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"publish": str(PUBLISH), "files": len(files), "total_bytes": manifest["total_bytes"]}, indent=2))


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--raw"]:
        raw_archive()
    elif sys.argv[1:] == ["--finish"]:
        finish()
    else:
        raise SystemExit("Usage: package.py --raw|--finish")
