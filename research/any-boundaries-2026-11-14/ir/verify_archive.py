"""Verify every archived metadata/raw member without extracting it to disk."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


metadata = {}
with tarfile.open(ROOT / "manifests-and-ledgers.tar.xz", "r:xz") as archive:
    for member in archive:
        assert member.isfile() and member.name not in metadata
        data = archive.extractfile(member).read()
        metadata[member.name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        if member.name == "metadata-files.json":
            expected_metadata = json.loads(data)
        elif member.name == "raw-files.json":
            expected_raw = json.loads(data)
assert set(metadata) == set(expected_metadata) | {"metadata-files.json"}
for name, value in expected_metadata.items():
    assert metadata[name] == value, name
seen = set()
with tarfile.open(ROOT / "raw-results.tar.xz", "r|xz") as archive:
    for member in archive:
        assert member.isfile() and member.name not in seen and member.name in expected_raw, member.name
        stream = archive.extractfile(member)
        digest = hashlib.sha256()
        size = 0
        while block := stream.read(131072):
            digest.update(block)
            size += len(block)
        assert {"sha256": digest.hexdigest(), "bytes": size} == expected_raw[member.name], member.name
        seen.add(member.name)
assert seen == set(expected_raw)
result = {"all_member_hashes_and_sizes_match": True, "metadata_members": len(metadata), "raw_members": len(seen),
          "raw_bytes": sum(item["bytes"] for item in expected_raw.values()),
          "raw_archive_sha256": sha(ROOT / "raw-results.tar.xz"),
          "metadata_archive_sha256": sha(ROOT / "manifests-and-ledgers.tar.xz"),
          "verification_script_sha256": sha(Path(__file__))}
(ROOT / "archive-verification.json").write_text(json.dumps(result, indent=2) + "\n")
manifest = json.loads((ROOT / "bundle-manifest.json").read_text())
manifest["files"] = {str(path.relative_to(ROOT)): {"sha256": sha(path), "bytes": path.stat().st_size}
                     for path in sorted(ROOT.rglob("*")) if path.is_file() and path.name != "bundle-manifest.json"}
manifest["total_bytes"] = sum(value["bytes"] for value in manifest["files"].values())
(ROOT / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(result, indent=2))
