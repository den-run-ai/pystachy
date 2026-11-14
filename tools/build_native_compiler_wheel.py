"""Create a local native-wheel pilot from a source wheel and a verified compiler.

This deliberately produces a local linux_x86_64 tag, not a manylinux claim.
No binary is compiled, downloaded, or published by this tool. It reuses a compiler
whose source/output identity was recorded by the local PGO experiment.
"""
import argparse
import base64
import csv
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import zipfile

from linux_abi import inspect_elf
from release import binary_target

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "_pystachy_source"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verified_binary(source, binary, manifest):
    manifest_bytes = manifest.read_bytes()
    evidence = json.loads(manifest_bytes)
    package_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    commit = evidence["source"]["commit"]
    if subprocess.run(["git", "merge-base", "--is-ancestor", commit, package_commit], cwd=source,
                      check=False, capture_output=True).returncode:
        raise ValueError("package source must descend from the compiler evidence commit")
    if not evidence["checks"]["ordinary-compiler-fixed-point"]["equal"]:
        raise ValueError("compiler lacks a successful ordinary fixed-point check")
    if binary.is_symlink() or not binary.is_file():
        raise ValueError("native binary must be a regular file")
    raw = binary.read_bytes()
    if sha256(raw) != evidence["bootstrap_binary_sha256"]:
        raise ValueError("binary differs from the bootstrapped compiler")
    for relative, expected in evidence["source"]["files"].items():
        if (PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts
                or "\\" in relative):
            raise ValueError("unsafe source identity path")
        if sha256((source / relative).read_bytes()) != expected:
            raise ValueError(f"package compiler/runtime source differs: {relative}")
    if binary_target(binary) != "linux-x86_64":
        raise ValueError("this local prototype supports only Linux x86_64")
    return raw, commit, package_commit, evidence, manifest_bytes


def load_source_wheel(wheel, source, evidence):
    if not wheel.name.endswith("-py3-none-any.whl"):
        raise ValueError("expected the ordinary py3-none-any source wheel")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError("duplicate wheel member")
        infos = {info.filename: info for info in archive.infolist()}
        for name, info in infos.items():
            if (PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                    or "\\" in name or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError("unsafe wheel member: " + name)
            if name.endswith(("/RECORD.jws", "/RECORD.p7s")):
                raise ValueError("cannot rewrite a signed wheel")
        data = {name: archive.read(name) for name in names}
    wheel_metadata = [name for name in names if name.endswith(".dist-info/WHEEL")]
    if len(wheel_metadata) != 1:
        raise ValueError("expected exactly one wheel metadata directory")
    directory = wheel_metadata[0].rsplit("/", 1)[0]
    metadata = BytesParser().parsebytes(data[directory + "/METADATA"])
    if metadata.get_all("Name") != ["pystachy"]:
        raise ValueError("expected a pystachy wheel")
    if wheel.name != f"pystachy-{metadata['Version']}-py3-none-any.whl":
        raise ValueError("source wheel filename and metadata version differ")
    if directory != f"pystachy-{metadata['Version']}.dist-info":
        raise ValueError("distribution path and metadata version differ")
    record_name = directory + "/RECORD"
    rows = list(csv.reader(io.StringIO(data[record_name].decode())))
    if {row[0] for row in rows} != set(names) or len(rows) != len(names):
        raise ValueError("ordinary wheel RECORD inventory differs")
    for name, checksum, length in rows:
        if name == record_name:
            continue
        expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data[name]).digest()).rstrip(b"=").decode()
        if checksum != expected or length != str(len(data[name])):
            raise ValueError("ordinary wheel RECORD mismatch: " + name)
    for relative, expected in evidence["source"]["files"].items():
        name = PACKAGE + "/" + relative
        required = (Path(relative).suffix in (".py", ".c", ".h")
                    and (relative.startswith(("src/", "lib/", "mpz/", "ryu/"))
                         or relative in ("pystachy.py", "runtime.py", "runtime.c", "pyembed.c", "pyext.c", "lljit.c")))
        if (name in data and sha256(data[name]) != expected) or (required and name not in data):
            raise ValueError("wheel lacks exact compiler/runtime input: " + relative)
    for relative in ("pystachy_cli.py", "pystachy_toolchain.py", "VERSION"):
        if data[PACKAGE + "/" + relative] != (source / relative).read_bytes():
            raise ValueError("wheel and source differ: " + relative)
    for relative in ("LICENSE", "THIRD_PARTY_NOTICES", "ryu/LICENSE-Boost"):
        if data[directory + "/licenses/" + relative] != (source / relative).read_bytes():
            raise ValueError("wheel license/notice changed or missing: " + relative)
    fields = BytesParser().parsebytes(data[wheel_metadata[0]])
    if fields.get_all("Tag") != ["py3-none-any"] or fields.get("Root-Is-Purelib") != "true":
        raise ValueError("source wheel has unexpected tags/install scheme")
    if any(name.startswith(PACKAGE + "/native/") for name in names):
        raise ValueError("ordinary wheel already contains a native payload")
    return data, infos, directory


def build(source, wheel, binary, manifest, output):
    raw, commit, package_commit, evidence, manifest_bytes = verified_binary(source, binary, manifest)
    data, infos, directory = load_source_wheel(wheel, source, evidence)
    abi = inspect_elf(binary)
    tracked_diff = subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=source)
    tracked_status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=source, text=True).splitlines()
    native = PACKAGE + "/native/pystachy"
    receipt_name = PACKAGE + "/native/manifest.json"
    receipt = {
        "schema": 1, "local_prototype": True,
        "source_commit": commit, "package_source_commit": package_commit, "native_sha256": sha256(raw),
        "native_bytes": len(raw), "source_wheel_sha256": sha256(wheel.read_bytes()),
        "baseline_manifest_sha256": sha256(manifest_bytes),
        "packaging_inputs_sha256": {p: sha256((source / p).read_bytes())
                                    for p in ("pystachy_cli.py", "pystachy_toolchain.py", "pyproject.toml")},
        "builder_sha256": sha256(Path(__file__).read_bytes()),
        "package_tracked_diff_sha256": sha256(tracked_diff),
        "package_tracked_changes": tracked_status,
        "tag": "py3-none-linux_x86_64", "abi": abi,
        "llvm": "External; existing package toolchain provisioning is retained",
        "licensing": "Existing Pystachy MIT and third-party notices retained; no Serc code imported",
    }
    data[native] = raw
    data[receipt_name] = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    data[PACKAGE + "/REVISION"] = (commit + "\n").encode()
    wname = directory + "/WHEEL"
    data[wname] = data[wname].replace(b"Root-Is-Purelib: true", b"Root-Is-Purelib: false").replace(
        b"Tag: py3-none-any", b"Tag: py3-none-linux_x86_64")
    record_name = directory + "/RECORD"
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for name in sorted(data):
        if name == record_name:
            continue
        value = data[name]
        checksum = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(value).digest()).rstrip(b"=").decode()
        writer.writerow([name, checksum, len(value)])
    writer.writerow([record_name, "", ""])
    data[record_name] = stream.getvalue().encode()
    output.mkdir(parents=True, exist_ok=True)
    destination = output / wheel.name.replace("-py3-none-any.whl", "-py3-none-linux_x86_64.whl")
    if destination.exists():
        raise ValueError("refusing to overwrite existing prototype wheel")
    timestamp = infos[wname].date_time
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(data):
            info = infos.get(name, zipfile.ZipInfo(name, date_time=timestamp))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name == native else 0o100644) << 16
            archive.writestr(info, data[name])
    result = receipt | {"wheel": str(destination), "wheel_sha256": sha256(destination.read_bytes()),
                        "wheel_bytes": destination.stat().st_size}
    destination.with_suffix(".baseline.json").write_bytes(manifest_bytes)
    destination.with_suffix(".json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--native-binary", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source.resolve(), args.wheel.resolve(), args.native_binary.absolute(),
                           args.baseline_manifest.resolve(), args.output.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
