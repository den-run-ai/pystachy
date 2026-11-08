"""Build a host-local Linux wheel for the schema-free JSON repair example and CLI."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile

import linux_abi
from json_repair_wheel_smoke import sha256, smoke

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/json_repair"
VERSION = "0.1.0.dev3"
PACKAGE = "pystachy_json_repair"
DIST = f"{PACKAGE}-{VERSION}"


def host_configuration():
    """The tag describes the running host; this builder does not cross-compile."""
    if sys.implementation.name != "cpython" or sys.version_info < (3, 12):
        raise ValueError("build this companion with CPython 3.12 or later")
    if sysconfig.get_config_var("Py_GIL_DISABLED") or not getattr(sys, "_is_gil_enabled", lambda: True)():
        raise ValueError("this abi3 companion requires a GIL-enabled CPython build")
    architecture = {"linux-x86_64": "x86_64"}.get(sysconfig.get_platform())
    if sys.platform != "linux" or architecture is None or platform.machine() != architecture:
        raise ValueError("build this companion on glibc Linux x86-64; cross-compilation is unsupported")
    try:
        libc = os.confstr("CS_GNU_LIBC_VERSION")
    except (AttributeError, OSError, ValueError):
        libc = None
    if not libc or not libc.startswith("glibc "):
        raise ValueError("this companion requires a glibc Linux host")
    return {"architecture": architecture, "tag": f"cp312-abi3-linux_{architecture}", "glibc": libc}


def prerequisites():
    if importlib.util.find_spec("wheel") is None:
        raise ValueError("install the wheel build tool with: python -m pip install -r tools/requirements-packaging.txt")
    if importlib.util.find_spec("ensurepip") is None:
        raise ValueError("install CPython's venv/ensurepip support for the isolated installed-wheel check")
    if shutil.which("readelf") is None:
        raise ValueError("install GNU readelf (binutils) to audit the native wheel payload")


def audit_payload(payload, host):
    report = linux_abi.audit(payload, architecture=host["architecture"])
    expected = {f"{PACKAGE}/_native.abi3.so", f"{DIST}.data/scripts/json-repair-native"}
    if {entry["path"] for entry in report["binaries"]} != expected:
        raise ValueError("the wheel must contain exactly the native extension and CLI ELF payloads")
    if report["violations"]:
        raise ValueError("invalid native wheel payload: " + "; ".join(report["violations"]))
    extension = next(entry for entry in report["binaries"] if entry["path"].endswith("/_native.abi3.so"))
    if extension["elf_type"] != "DYN":
        raise ValueError("the native extension must be an ELF shared object")
    report["wheel_tag"] = host["tag"]
    report["build_host"] = {"glibc": host["glibc"], "python": sys.version, "platform": sysconfig.get_platform()}
    return report


def publish(wheel, evidence, out):
    """Serialize Linux publishers and roll back an incomplete replacement pair."""
    import fcntl

    # Keep this inode: deleting a lock file can let a later publisher lock a new
    # inode while an earlier waiter still holds the old one.
    with (out / f".{wheel.name}.publish.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        report = json.loads(evidence.read_text(encoding="utf-8"))
        if report["installation"]["wheel_sha256"] != sha256(wheel):
            raise ValueError("wheel changed after its installed validation")
        backup = Path(tempfile.mkdtemp(prefix=".json-repair-publish-", dir=out))
        remove_backup = True
        targets = [(wheel, out / wheel.name), (evidence, out / evidence.name)]
        previous = {}
        attempted = []
        try:
            for _, target in targets:
                previous[target] = backup / target.name if target.exists() else None
                if previous[target] is not None:
                    shutil.copy2(target, previous[target])
            try:
                for source, target in targets:
                    attempted.append(target)
                    source.replace(target)
            except BaseException:
                try:
                    for target in reversed(attempted):
                        saved = previous[target]
                        if saved is None:
                            target.unlink(missing_ok=True)
                        else:
                            saved.replace(target)
                except BaseException as error:
                    remove_backup = False
                    raise RuntimeError(f"could not restore the prior wheel/report; backups retained in {backup}") from error
                raise
        finally:
            if remove_backup:
                shutil.rmtree(backup)


def build(out):
    host = host_configuration()
    prerequisites()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as temp:
        staging = Path(temp)
        payload = staging / "wheel"
        package = payload / PACKAGE
        scripts = payload / f"{DIST}.data/scripts"
        info = payload / f"{DIST}.dist-info"
        licenses = info / "licenses"
        for directory in (package, scripts, licenses):
            directory.mkdir(parents=True)
        shutil.copyfile(EXAMPLE / PACKAGE / "__init__.py", package / "__init__.py")

        compiler = [sys.executable, str(ROOT / "pystachy.py")]
        env = os.environ | {"PYSTACHY_HOME": str(ROOT), "PYSTACHY_PATH": str(ROOT / "ports")}
        subprocess.run([*compiler, "ext", EXAMPLE / "_native.py", "-o", package / "_native.abi3.so"],
                       env=env, cwd=ROOT, check=True)
        subprocess.run([*compiler, "build", EXAMPLE / "repair.py", "-o", scripts / "json-repair-native"],
                       env=env, cwd=ROOT, check=True)
        abi = audit_payload(payload, host)
        (info / "native-abi.json").write_text(json.dumps(abi, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        for path in ("LICENSE", "THIRD_PARTY_NOTICES", "ports/json_repair/LICENSE",
                     "tests/upstream/CPYTHON-LICENSE.txt", "ryu/LICENSE-Boost"):
            target = licenses / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)
        # mpz.c carries the original MicroPython copyright and permission notice.
        header, end, _ = (ROOT / "mpz/mpz.c").read_bytes().partition(b"*/")
        if not end or b"Permission is hereby granted" not in header:
            raise ValueError("missing mpz.c license header")
        (licenses / "MICROPYTHON-LICENSE").write_bytes(header + end + b"\n")
        metadata = ("Metadata-Version: 2.4\nName: pystachy-json-repair\n"
                    f"Version: {VERSION}\nSummary: Native schema-free JSON repair\nRequires-Python: >=3.12\n")
        for path in sorted(licenses.rglob("*")):
            if path.is_file():
                metadata += f"License-File: {path.relative_to(licenses).as_posix()}\n"
        (info / "METADATA").write_text(metadata, encoding="utf-8")
        (info / "WHEEL").write_text(f"Wheel-Version: 1.0\nGenerator: Pystachy\n"
                                    f"Root-Is-Purelib: false\nTag: {host['tag']}\n", encoding="utf-8")
        subprocess.run([sys.executable, "-m", "wheel", "pack", payload, "--dest-dir", staging], check=True)
        filename = f"{DIST}-{host['tag']}.whl"
        wheel = staging / filename
        validation = {"schema_version": 1, "abi": abi, "installation": smoke(wheel)}
        evidence = wheel.with_suffix(".validation.json")
        evidence.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # The complete wheel includes its ELF report. Publish only after the
        # installed checks succeed; a failed rebuild leaves any prior wheel intact.
        publish(wheel, evidence, out)
    print(out / filename)
    return out / filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="destination wheel directory")
    try:
        build(parser.parse_args().out.resolve())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"json-repair wheel: {error}\n")
