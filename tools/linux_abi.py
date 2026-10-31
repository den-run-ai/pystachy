"""Inspect ELF dependencies and required symbol versions without executing payloads.

This is a release diagnostic, not a manylinux certification tool. It scans every
ELF file in an extracted artifact, including bundled shared libraries. External
libraries, dlopen dependencies, CPU instructions and runtime behavior need separate
validation. GNU readelf (binutils) is required; the payload is never run via ldd.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess


MACHINES = {62: "x86_64", 183: "aarch64"}
LIMITS = [
    "Required ELF symbol versions are a lower bound, not proof of runtime compatibility.",
    "External libraries and dependencies loaded with dlopen are not resolved or audited.",
    "CPU instruction requirements, kernel requirements and manylinux wheel policy are not checked.",
    "Generated AOT programs and external LLVM tools require their own audits and execution tests.",
]


def version_tuple(value):
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", value):
        raise ValueError(f"invalid version: {value}")
    return tuple(int(part) for part in value.split("."))


def parse_readelf(text):
    """Read requirements only: version definitions are provided, not imported."""
    needed = sorted(set(re.findall(r"\(NEEDED\).*?\[([^\]]+)\]", text)))
    paths = re.findall(r"\((RPATH|RUNPATH)\).*?\[([^\]]*)\]", text)
    interpreter = re.search(r"\[Requesting program interpreter: ([^\]]+)\]", text)
    versions = {}
    in_needs = False
    library = None
    for line in text.splitlines():
        if line.startswith("Version "):
            in_needs = line.startswith("Version needs section ")
            library = None
        if not in_needs:
            continue
        file_match = re.search(r"\bFile:\s+(\S+)", line)
        if file_match:
            library = file_match.group(1)
            versions.setdefault(library, set())
        name_match = re.search(r"\bName:\s+(\S+)", line)
        if name_match:
            if library is None:
                raise ValueError("readelf reported a required version without a library")
            versions[library].add(name_match.group(1))
    # Never silently interpret an unparsed version-needs table as no requirements.
    if "(VERNEED)" in text and not versions:
        raise ValueError("readelf did not expose the ELF version-needs table")
    return {
        "needed": needed,
        "version_needs": {name: sorted(values) for name, values in sorted(versions.items())},
        "interpreter": interpreter.group(1) if interpreter else None,
        "search_paths": [{"tag": tag, "path": value} for tag, value in paths],
    }


def inspect_elf(path):
    with path.open("rb") as handle:
        header = handle.read(64)
    if len(header) < 64 or header[:7] != b"\x7fELF\x02\x01\x01":
        raise ValueError(f"expected a little-endian ELF64 file: {path}")
    kind, machine = struct.unpack("<HH", header[16:20])
    if machine not in MACHINES or kind not in (2, 3):
        raise ValueError(f"unsupported ELF type/machine ({kind}/{machine}): {path}")
    result = subprocess.run(
        ["readelf", "--wide", "--program-headers", "--dynamic", "--version-info", str(path)],
        env={**os.environ, "LC_ALL": "C"}, text=True, capture_output=True, check=True, timeout=30,
    )
    if result.stderr.strip():
        raise ValueError(f"readelf diagnostics for {path}: {result.stderr.strip()}")
    data = parse_readelf(result.stdout)
    required = {value for values in data["version_needs"].values() for value in values}
    glibc = [value[6:] for value in required if re.fullmatch(r"GLIBC_[0-9]+(?:\.[0-9]+)+", value)]
    data["glibc_symbol_floor"] = max(glibc, key=version_tuple) if glibc else None
    data["non_numeric_glibc"] = sorted(value for value in required if value.startswith("GLIBC_") and value[6:] not in glibc)
    data["architecture"] = MACHINES[machine]
    data["elf_type"] = "EXEC" if kind == 2 else "DYN"
    with path.open("rb") as handle:
        data["sha256"] = hashlib.file_digest(handle, "sha256").hexdigest()
    return data


def audit(root, architecture=None, max_glibc=None):
    root = root.resolve(strict=True)
    ceiling = version_tuple(max_glibc) if max_glibc else None
    entries = [root] if root.is_file() else sorted(root.rglob("*"))
    binaries = []
    violations = []
    for path in entries:
        # Release resources currently prohibit symlinks. Refuse to omit linked
        # payloads or accidentally inspect dependencies outside the supplied tree.
        if path.is_symlink():
            raise ValueError(f"audit requires real files/directories, not symlinks: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"not a regular artifact file: {path}")
        with path.open("rb") as handle:
            if handle.read(4) != b"\x7fELF":
                continue
        data = inspect_elf(path)
        name = path.name if root.is_file() else path.relative_to(root).as_posix()
        data["path"] = name
        binaries.append(data)
        if architecture and data["architecture"] != architecture:
            violations.append(f"{name}: architecture {data['architecture']} differs from {architecture}")
        floor = data["glibc_symbol_floor"]
        if ceiling and floor and version_tuple(floor) > ceiling:
            violations.append(f"{name}: requires GLIBC_{floor}, above ceiling GLIBC_{max_glibc}")
        if ceiling and data["non_numeric_glibc"]:
            violations.append(f"{name}: cannot bound private/non-numeric GLIBC requirements: {data['non_numeric_glibc']}")
    if not binaries:
        raise ValueError(f"no ELF binaries found: {root}")
    return {
        "schema_version": 1, "expected_architecture": architecture, "max_glibc": max_glibc,
        "elf_count": len(binaries), "binaries": binaries, "violations": violations,
        "limitations": LIMITS,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="native binary or complete extracted release directory")
    parser.add_argument("--architecture", choices=sorted(MACHINES.values()))
    parser.add_argument("--max-glibc", help="fail if imported GLIBC symbols exceed this version, e.g. 2.28")
    parser.add_argument("--json", type=Path, help="also retain the report at this path")
    args = parser.parse_args()
    try:
        report = audit(args.path, args.architecture, args.max_glibc)
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.json:
            args.json.write_text(encoded, encoding="utf-8")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(2, f"linux-abi: {error}\n")
    print(encoded, end="")
    if report["violations"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
