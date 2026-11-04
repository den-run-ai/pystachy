"""Build a host-local Linux wheel for the schema-free JSON repair example and CLI."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/json_repair"
VERSION = "0.1.0.dev2"
PACKAGE = "pystachy_json_repair"
DIST = f"{PACKAGE}-{VERSION}"
TAG = "cp312-abi3-linux_x86_64"


def build(out):
    if sysconfig.get_platform() != "linux-x86_64" or not os.confstr("CS_GNU_LIBC_VERSION"):
        raise SystemExit("build this example on Linux x86-64 with glibc")
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
                                    f"Root-Is-Purelib: false\nTag: {TAG}\n", encoding="utf-8")
        subprocess.run([sys.executable, "-m", "wheel", "pack", payload, "--dest-dir", staging], check=True)
        filename = f"{DIST}-{TAG}.whl"
        (staging / filename).replace(out / filename)
    print(out / filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="destination wheel directory")
    build(parser.parse_args().out.resolve())
