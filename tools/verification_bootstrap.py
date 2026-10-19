#!/usr/bin/env python3
"""Export/restore a verified bootstrap within one CI run, without runtime caches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import tempfile

from merge_verification import invalid_constant, unique_object, validate_report

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ("stage1.ll", "rt1.ll", "rt2.ll", "bootstrap.log", "pystachy2")
TOOLS = ("clang", "opt", "llvm-as", "llvm-link", "lli")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def read_file(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"not a regular file: {path}")
    return path.read_bytes()


def read_json(data):
    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def command(root, *args):
    return subprocess.run(args, cwd=root, check=True, capture_output=True, timeout=30).stdout


def identity(root):
    """Use working-tree bytes, not index blobs; checkout paths and runner CPUs may differ."""
    tracked = command(root, "git", "ls-files", "-z").split(b"\0")
    source_hash = hashlib.sha256()
    for name in sorted(name for name in tracked if name):
        path = root / os.fsdecode(name)
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            # The test corpus deliberately includes dangling links and loops. Bind link
            # identity without following it, just as Git does.
            data, kind = os.fsencode(os.readlink(path)), b"120000"
        else:
            data = read_file(path)
            kind = b"100755" if mode & 0o111 else b"100644"
        source_hash.update(name + b"\0" + kind + b"\0" + digest(data).encode() + b"\0")
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    versions = {name: command(root, str(Path(llvm) / name) if llvm else name, "--version")
                .decode().splitlines()[0] for name in TOOLS}
    release = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        key, _, value = line.partition("=")
        if key in ("ID", "VERSION_ID"):
            release[key] = value.strip('"')
    if platform.system() != "Linux" or not release:
        raise ValueError("bootstrap reuse requires an identified Linux ABI")
    return {"commit": command(root, "git", "rev-parse", "HEAD").decode().strip(),
            "tracked_sources_sha256": source_hash.hexdigest(),
            "system": platform.system(), "machine": platform.machine(), "os": release,
            "libc": os.confstr("CS_GNU_LIBC_VERSION"), "tools": versions,
            "python": sys.version, "python_implementation": sys.implementation.name,
            "python_version": platform.python_version(),
            "github_run_id": os.environ.get("GITHUB_RUN_ID", "")}


def validate_producer(report, current, root):
    if not isinstance(report, dict) or report.get("group") != "bootstrap":
        raise ValueError("expected a bootstrap-only producer report")
    validate_report(report, "bootstrap", ["bootstrap"])
    if report["steps"][0].get("bootstrap_reused") is True:
        raise ValueError("producer must perform its own bootstrap")
    if report["git"]["commit"] != current["commit"]:
        raise ValueError("producer commit differs from checkout")
    toolchain = report["toolchain"]
    expected = {"python": "Python " + current["python_version"],
                "clang": current["tools"]["clang"], "llvm": current["tools"]["opt"]}
    if any(toolchain.get(key) != value for key, value in expected.items()):
        raise ValueError("producer toolchain differs from checkout")
    if report.get("platform", {}).get("machine") != current["machine"]:
        raise ValueError("producer architecture differs from checkout")
    paths = [root / name for name in ("pystachy.py", "runtime.c", "runtime.py")]
    paths += sorted((root / "src").rglob("*.py"))
    for path in paths:
        data = read_file(path)
        expected = {"lines": data.count(b"\n"), "sha256": digest(data)}
        if report["sources"].get(path.relative_to(root).as_posix()) != expected:
            raise ValueError(f"producer source differs: {path.relative_to(root)}")


def validate_payload(report, files):
    step = report["steps"][0]
    if (digest(files["stage1.ll"]) != step.get("ir_sha256") or
            files["stage1.ll"].count(b"\n") != step.get("ir_lines")):
        raise ValueError("compiler IR differs from producer evidence")
    if len(files["pystachy2"]) != step.get("native_compiler_bytes"):
        raise ValueError("compiler size differs from producer evidence")
    if (step.get("runtime_ir_identical") is not True or
            digest(files["rt1.ll"]) != step.get("runtime_ir_sha256") or
            files["rt1.ll"] != files["rt2.ll"]):
        raise ValueError("runtime IR differs from producer evidence")
    if any(not files[name] for name in PAYLOAD):
        raise ValueError("empty bootstrap payload")


def write_file(path, data, executable=False):
    # Replace instead of following an existing file's symlink; no executable appears before
    # validation completes, and a partial write can never become the restored compiler.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temporary = Path(temp.name)
        try:
            temp.write(data)
            temp.flush()
            os.chmod(temporary, 0o755 if executable else 0o644)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def export_bundle(directory, root=ROOT):
    current = identity(root)
    report_path = root / "build/verification.json"
    report = read_json(read_file(report_path))
    validate_producer(report, current, root)
    work = root / "build/verify"
    files = {name: read_file(work / name) for name in PAYLOAD}
    # Recheck both fixed points, including the two stages not needed by consumer jobs.
    for prefix, reference in (("stage", "stage1.ll"), ("rt", "rt1.ll")):
        if any(read_file(work / f"{prefix}{index}.ll") != files[reference] for index in (2, 3)):
            raise ValueError(f"{prefix} bootstrap fixed point differs")
    step = report["steps"][0]
    step.update(runtime_ir_identical=True, runtime_ir_sha256=digest(files["rt1.ll"]))
    validate_payload(report, files)
    # The bundled report precedes bundle annotations, avoiding a circular digest. The
    # authoritative producer report gets the manifest ID after all bundle files are written.
    files["verification.json"] = canonical(report)
    manifest = {"schema": 1, "identity": current,
                "sha256": {name: digest(data) for name, data in files.items()}}
    manifest_bytes = canonical(manifest)
    bundle_id = digest(manifest_bytes)
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError("bundle destination must be empty")
    for name, data in files.items():
        write_file(directory / name, data)
    write_file(directory / "manifest.json", manifest_bytes)
    step.update(bootstrap_bundle_id=bundle_id, bootstrap_reused=False,
                producer_seconds=step["seconds"])
    write_file(report_path, canonical(report) + b"\n")
    return bundle_id


def restore_bundle(directory, root=ROOT):
    manifest_bytes = read_file(directory / "manifest.json")
    manifest = read_json(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise ValueError("unsupported bootstrap manifest")
    current = identity(root)
    if manifest.get("identity") != current:
        raise ValueError("bootstrap checkout, toolchain, ABI or workflow run identity differs")
    expected = {*PAYLOAD, "verification.json"}
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or set(hashes) != expected:
        raise ValueError("unexpected bootstrap payload filenames")
    files = {name: read_file(directory / name) for name in expected}
    for name, data in files.items():
        if digest(data) != hashes[name]:
            raise ValueError(f"bootstrap payload digest differs: {name}")
    report = read_json(files["verification.json"])
    validate_producer(report, current, root)
    validate_payload(report, files)
    fields = {key: value for key, value in report["steps"][0].items()
              if key not in ("name", "result", "seconds", "log")}
    fields.update(bootstrap_bundle_id=digest(manifest_bytes), bootstrap_reused=True,
                  producer_seconds=report["steps"][0]["seconds"])
    work = root / "build/verify"
    if work.parent.is_symlink() or work.is_symlink():
        raise ValueError("bootstrap destination must not be a symlink")
    work.mkdir(parents=True, exist_ok=True)
    for name in PAYLOAD:
        write_file(work / name, files[name], executable=name == "pystachy2")
    write_file(work / "bootstrap-reuse.json", canonical(fields) + b"\n")
    return fields


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "restore"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        result = (export_bundle if args.action == "export" else restore_bundle)(args.directory)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"bootstrap bundle: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
