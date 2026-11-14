#!/usr/bin/env python3
"""Package frozen Lean evidence, or verify a published package without running tests."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def mode(path):
    return "100755" if path.stat().st_mode & 0o111 else "100644"


def relative_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or str(path) != name:
        raise ValueError(f"unsafe or noncanonical path: {name}")
    if not path.parts or name in ("manifest.json", "SHA256SUMS"):
        raise ValueError(f"reserved path: {name}")
    return path


def read_frozen(entry):
    path = Path(entry["source_path"])
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"not a regular source file: {path}")
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise ValueError(f"source changed while reading: {path}")
    if len(data) != entry["original_bytes"] or digest(data) != entry["original_sha256"]:
        raise ValueError(f"frozen source digest mismatch: {path}")
    if mode(path) != entry["mode"]:
        raise ValueError(f"frozen source mode mismatch: {path}")
    if data.startswith(b"\x7fELF"):
        raise ValueError(f"reproducible executable is not publication evidence: {path}")
    return data


def verify(bundle):
    bundle = Path(bundle)
    manifest = json.loads((bundle / "manifest.json").read_text())
    if manifest["schema"] != 1 or manifest["completion"]["immutable"] is not True:
        raise ValueError("not a completed immutable evidence package")
    if not all(manifest["completion"].get(key) is True for key in (
        "canonical_report_complete", "strict_storage_complete"
    )):
        raise ValueError("canonical report or strict storage is incomplete")
    expected = {"manifest.json", "SHA256SUMS"}
    for entry in manifest["files"]:
        name = str(relative_path(entry["path"]))
        if name in expected:
            raise ValueError(f"duplicate package path: {name}")
        expected.add(name)
        path = bundle / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"not a regular package file: {path}")
        data = path.read_bytes()
        if len(data) != entry["stored_bytes"] or digest(data) != entry["stored_sha256"]:
            raise ValueError(f"stored file changed: {name}")
        if git_blob(data) != entry["git_blob_sha"] or mode(path) != entry["mode"]:
            raise ValueError(f"Git identity or mode mismatch: {name}")
        encoding = entry["encoding"]
        if encoding == "gzip-mtime-0-level-9":
            original = gzip.decompress(data)
            if gzip.compress(original, compresslevel=9, mtime=0) != data:
                raise ValueError(f"noncanonical gzip encoding: {name}")
        elif encoding == "identity":
            original = data
        else:
            raise ValueError(f"unknown encoding: {encoding}")
        if len(original) != entry["original_bytes"] or digest(original) != entry["original_sha256"]:
            raise ValueError(f"original file does not match manifest: {name}")
    actual = {str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError(f"package membership mismatch: {sorted(actual ^ expected)}")
    sums = "".join(
        f"{digest((bundle / name).read_bytes())}  {name}\n"
        for name in sorted(expected - {"SHA256SUMS"})
    )
    if (bundle / "SHA256SUMS").read_text() != sums:
        raise ValueError("SHA256SUMS mismatch")
    return {
        "verified": True,
        "file_count": len(expected),
        "stored_bytes": sum((bundle / name).stat().st_size for name in expected),
        "manifest_sha256": digest((bundle / "manifest.json").read_bytes()),
        "sha256sums_sha256": digest((bundle / "SHA256SUMS").read_bytes()),
        "source_commit": manifest["source_commit"],
        "source_tree": manifest["source_tree"],
        "completion": manifest["completion"],
    }


def build(plan_path):
    plan_path = Path(plan_path).resolve()
    plan_data = plan_path.read_bytes()
    plan = json.loads(plan_data)
    if plan["schema"] != 1 or plan["completion"]["immutable"] is not True:
        raise ValueError("explicit immutable completion receipt is required")
    if not all(plan["completion"].get(key) is True for key in (
        "canonical_report_complete", "strict_storage_complete"
    )):
        raise ValueError("both canonical report and strict storage must be complete")
    bundle = Path(plan["bundle_path"])
    if bundle.exists():
        raise ValueError(f"refusing to overwrite an existing package: {bundle}")
    if len({entry["path"] for entry in plan["files"]}) != len(plan["files"]):
        raise ValueError("duplicate destination in frozen plan")
    staging = Path(tempfile.mkdtemp(prefix="package-staging-", dir=plan_path.parent))
    records = []
    try:
        for entry in plan["files"]:
            name = str(relative_path(entry["path"]))
            data = read_frozen(entry)
            encoding = entry["encoding"]
            if encoding == "gzip-mtime-0-level-9":
                stored = gzip.compress(data, compresslevel=9, mtime=0)
            elif encoding == "identity":
                stored = data
            else:
                raise ValueError(f"unsupported encoding: {encoding}")
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(stored)
            path.chmod(0o755 if entry["mode"] == "100755" else 0o644)
            records.append({
                **entry,
                "stored_bytes": len(stored),
                "stored_sha256": digest(stored),
                "git_blob_sha": git_blob(stored),
            })
        manifest = {key: value for key, value in plan.items() if key not in ("files", "bundle_path")}
        manifest.update({
            "packaging_plan_sha256": digest(plan_data),
            "files": records,
            "packaging_note": "Copies frozen output bytes; does not execute or modify verification inputs.",
        })
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        (staging / "manifest.json").chmod(0o644)
        names = sorted(str(p.relative_to(staging)) for p in staging.rglob("*") if p.is_file())
        (staging / "SHA256SUMS").write_text("".join(
            f"{digest((staging / name).read_bytes())}  {name}\n" for name in names
        ))
        (staging / "SHA256SUMS").chmod(0o644)
        result = verify(staging)
        for entry in plan["files"]:
            read_frozen(entry)
        if plan_path.read_bytes() != plan_data:
            raise ValueError("packaging plan changed during build")
        bundle.parent.mkdir(parents=True, exist_ok=True)
        os.rename(staging, bundle)
        return {"bundle": str(bundle), **result}
    except BaseException:
        shutil.rmtree(staging)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("path")
    args = parser.parse_args()
    result = build(args.path) if args.action == "build" else verify(args.path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
