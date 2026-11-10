"""Save an Actions artifact verbatim and verify every reported committed source."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile


parser = argparse.ArgumentParser()
parser.add_argument("--directory", type=Path, required=True)
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--head", required=True)
parser.add_argument("--platform", choices=("linux", "macos"), required=True)
args = parser.parse_args()
request = json.load(sys.stdin)
artifact = request["artifact"]
assert artifact["workflow_run"]["head_sha"] == args.head
args.directory.mkdir(parents=True, exist_ok=True)
archive_path = args.directory / ("netio-" + args.platform + ".zip")
data = urllib.request.urlopen(request["download_url"], timeout=60).read()
digest = hashlib.sha256(data).hexdigest()
assert artifact["digest"] == "sha256:" + digest
assert not archive_path.exists(), archive_path
archive_path.write_bytes(data)
(args.directory / (args.platform + "-artifact-metadata.json")).write_text(
    json.dumps(artifact, indent=2) + "\n")
reports = []
all_paths = set()
with zipfile.ZipFile(archive_path) as archive:
    for name in archive.namelist():
        assert Path(name).name == name and name.endswith(".json"), name
        raw = archive.read(name)
        destination = args.directory / name
        assert not destination.exists(), destination
        destination.write_bytes(raw)
        report = json.loads(raw)
        expected = {}
        for field in ("source_sha256", "compiler_source_sha256"):
            for path, source_digest in report.get(field, {}).items():
                if field == "source_sha256" and not path.startswith(("examples/", "tools/")):
                    path = "examples/netio/" + path
                if path in expected:
                    assert expected[path] == source_digest, path
                expected[path] = source_digest
        for field, path in (("drain_sha256", "examples/netio/drain.py"),
                            ("checker_sha256", "examples/netio/check_drain.py"),
                            ("probe_sha256", "examples/netio/drain_probe.py")):
            if field in report:
                expected[path] = report[field]
        for path, source_digest in expected.items():
            source = subprocess.check_output(["git", "show", args.head + ":" + path], cwd=args.repo)
            assert hashlib.sha256(source).hexdigest() == source_digest, path
        all_paths.update(expected)
        record = {"file": name, "file_sha256": hashlib.sha256(raw).hexdigest(),
                  "result": report["result"], "source_hashes_verified": len(expected),
                  "source_paths": sorted(expected), "platform": report.get("platform"),
                  "python": report.get("python")}
        for field in ("modes", "runs", "cases", "repeat", "compiler", "scenario", "error"):
            if field in report:
                record[field] = report[field]
        reports.append(record)
metadata_path = args.directory / "qualification-metadata.json"
metadata = json.loads(metadata_path.read_text())
expected_names = ({"netio-macos.json", "netio-drain-macos.json"} if args.platform == "macos" else
                  {"netio-linux-benchmark-smoke.json", "netio-linux-hosted.json",
                   "netio-linux-native.json", "netio-linux-drain-hosted.json",
                   "netio-linux-drain-native.json"})
missing = sorted(expected_names - {r["file"] for r in reports})
metadata[args.platform].update({
    "artifact_id": artifact["id"], "artifact_name": artifact["name"],
    "workflow_run": artifact["workflow_run"]["id"], "archive": archive_path.name,
    "archive_sha256": digest, "archive_digest_verified": True,
    "artifact_created_at": artifact["created_at"], "reports": reports,
    "unique_source_paths_verified": len(all_paths),
    "missing_reports": missing,
    "status": ("reports_pass" if not missing and all(r["result"] == "pass" for r in reports)
               else "reports_incomplete_or_failed"),
})
metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps({"archive": str(archive_path), "archive_sha256": digest,
                  "reports": [{k: r[k] for k in ("file", "result", "source_hashes_verified")}
                              for r in reports], "unique_sources": len(all_paths)}))
