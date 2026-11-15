"""Freeze historical blocked-census and reviewed repair evidence for GitHub."""
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
INITIAL = ROOT / "research-publish/initial-v2"
OUT = ROOT / "research-publish/storage-repair-checkpoint"
assert not OUT.exists()
acceptance = json.loads((ROOT / "evidence/lean-corrected/acceptance.json").read_text())
assert acceptance["programs"] == 2699 and acceptance["storage_programs"] == 196
assert not acceptance["checks"]["strict_storage_all_accepted"]
assert all(v for k, v in acceptance["checks"].items() if k != "strict_storage_all_accepted")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def put(name, data):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())


def copy(source, target):
    put(target, (ROOT / source).read_bytes())


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


shutil.copytree(INITIAL, OUT)
(OUT / "upload-manifest.json").unlink()
(OUT / "SHA256SUMS").unlink()
copies = {
    "evidence/storage-repair-checkpoint-README.md": "README.md",
    "evidence/lean/optional-storage-repair/diagnosis-and-validation.md": "optional-storage-repair.md",
    "evidence/lean/optional-storage-repair/frozen-repair.json": "optional-storage-repair.json",
    "evidence/lean/optional-storage-repair/published-repair.json": "optional-storage-published.json",
    "evidence/lean/optional-storage-repair/root-review.md": "reviews/optional-storage-root.md",
    "evidence/lean/optional-storage-repair/independent-review.md": "reviews/optional-storage-independent.md",
    "evidence/lean/optional-storage-repair/final-source-equivalence-b0-to-0a2f.json": "final-source-equivalence.json",
    "evidence/lean/optional-storage-repair/final-source-equivalence-b0-to-0a2f.md": "final-source-equivalence.md",
    "evidence/ci/pr1494-bbc/qualification.json": "integrated-pr-checks.json",
    "evidence/ci/pr1494-bbc/qualification.md": "integrated-pr-checks.md",
    "evidence/ci/b0-native-coverage/all-residual-coverage.md": "residual-native-coverage.md",
    "evidence/lean-corrected/added-complex-residual-review/review.md": "complex-residuals.md",
    "qualification-tools/pack-storage-checkpoint.py": "pack-storage-checkpoint.py",
}
for name in ("report.md", "acceptance.json", "delta-alpha2.json", "complete-blocked-census.json",
             "historical-attempt-comparison.json"):
    copies["evidence/lean-corrected/" + name] = "lean-94/" + name
for name in ("accepted-ir-review.md", "full-disposition.md", "tomllib-guard-attribution-correction.md"):
    copies["evidence/ir-review/" + name] = "ir/" + name
for source, target in copies.items():
    copy(source, target)

def files(directory):
    return [p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts]

blocked = files("evidence/lean-corrected")
blocked += files("evidence/lean/tomllib-count-attribution-support")
blocked += files("evidence/lean/complex-copy-gc-independent-review")
bundle("lean-94-complete-blocked.tar.gz", blocked)
bundle("optional-storage-repair.tar.gz", files("evidence/lean/optional-storage-repair"))
ci = [p for p in files("evidence/ci") if p.suffix not in {".zip", ".gz"} and "pr1501" not in p.parts]
bundle("workflow-evidence-through-bbc.tar.gz", ci)
corrections = [ROOT / "evidence/ir-review" / name for name in
               ("accepted-ir-review.json", "accepted-ir-review.md", "full-disposition.json",
                "full-disposition.md", "assemble-dispositions.py", "tomllib-guard-attribution-correction.json",
                "tomllib-guard-attribution-correction.md")]
corrections += files("evidence/ir-review/correction-history")
bundle("ir-attribution-correction.tar.gz", corrections)
baseline_path = Path("/workspace/scratch/7dd0519bc14a/lean-reports/alpha2-storage-lean-records.jsonl")
baseline = baseline_path.read_bytes()
assert digest(baseline) == "98d2cd703064e39dbb14e41f3d13bb1b5df7bbcf4d30903966db4b427ecd09a6"
put("alpha2-baseline-records.jsonl.gz", gzip.compress(baseline, mtime=0))
put("alpha2-baseline-records-identity.json", json.dumps({"source_path": str(baseline_path),
    "uncompressed_bytes": len(baseline), "uncompressed_sha256": digest(baseline),
    "source_commit": "950c0440ad793dc6c34664f591383a5e6bba14dd",
    "published_alpha2_commit": "80490143498d149d407343ba1cb7aedb1db2d2c5",
    "equivalent_tree": "717a8c9386ae9f5f6545cc3686a9e22282fc560c"}, indent=2) + "\n")

manifest = []
for path in sorted(OUT.rglob("*")):
    if path.is_file():
        data = path.read_bytes()
        manifest.append({"path": str(path.relative_to(OUT)), "bytes": len(data), "sha256": digest(data),
                         "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
put("SHA256SUMS", "".join(f"{r['sha256']}  {r['path']}\n" for r in manifest))
data = (OUT / "SHA256SUMS").read_bytes()
manifest.append({"path": "SHA256SUMS", "bytes": len(data), "sha256": digest(data),
                 "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
prior = {r["path"]: r["git_blob"] for r in json.loads((INITIAL / "upload-manifest.json").read_text())["files"]}
changed = [r for r in manifest if prior.get(r["path"]) != r["git_blob"]]
put("upload-manifest.json", json.dumps({"created_utc": datetime.now(timezone.utc).isoformat(),
    "root": str(OUT), "files": manifest, "changed": changed,
    "expected_research_head": "7d8abcf65b31147db09f27d18481815e98c967d8",
    "expected_research_tree": "38af55327f3b5fc5420c39c7e4888ceb2ab7aba1"}, indent=2) + "\n")
print(json.dumps({"root": str(OUT), "files": len(manifest), "changed_files": len(changed),
                  "changed_bytes": sum(r["bytes"] for r in changed)}, indent=2))
