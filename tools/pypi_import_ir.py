"""Replay pinned, isolated root-wheel import compilations on multiple native compilers.

Input JSONL records carry rank, project, version, import, filename and sha256. Wheels
must already exist in the wheelhouse. This lane does not install or execute packages.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
import keyword
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
import zipfile

from import_sweep import compiler_sha256, source_git
from pypi_inventory import MAX_WHEEL


def wheel_source(row, wheelhouse, site):
    filename = row["filename"]
    if PureWindowsPath(filename).name != filename or PurePosixPath(filename).name != filename or not filename.endswith(".whl"):
        raise ValueError(f"unsafe wheel filename: {filename!r}")
    with (wheelhouse / filename).open("rb") as stream:
        data = stream.read(MAX_WHEEL + 1)
    if len(data) > MAX_WHEEL or hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError(f"wheel exceeds size limit or SHA-256 differs: {filename}")
    total = 0
    with zipfile.ZipFile(BytesIO(data)) as wheel:
        for entry in wheel.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in entry.filename or ":" in entry.filename:
                raise ValueError(f"unsafe wheel entry: {entry.filename!r}")
            if path.suffix != ".py":
                continue
            parts = path.parts
            if parts[0].endswith(".data"):
                if len(parts) < 3 or parts[1] not in ("purelib", "platlib"):
                    continue
                parts = parts[2:]
            if parts[0].endswith(".dist-info"):
                continue
            total += entry.file_size
            if total > 128 * 1024**2:
                raise ValueError(f"wheel source exceeds size limit: {filename}")
            dest = site.joinpath(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with wheel.open(entry) as src, dest.open("xb") as dst:
                shutil.copyfileobj(src, dst)


def compile_ir(compiler, env, driver, timeout):
    ir = driver.with_suffix(".ll")
    ir.unlink(missing_ok=True)
    try:
        proc = subprocess.run([compiler, "ir", driver, "-o", ir], cwd=driver.parent, env=env,
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    if proc.returncode == 0 and ir.is_file() and ir.stat().st_size > 0 and not proc.stderr and not proc.stdout:
        return {"status": "ir"}
    diagnostic = (proc.stderr or proc.stdout).decode(errors="replace").strip()
    diagnostic = diagnostic.replace(env["PYSTACHY_PATH"], "WHEEL").replace(env["PYSTACHY_HOME"], "COMPILER")
    diagnostic = diagnostic.replace(str(driver.parent), "WORK")
    status = "rejected" if proc.returncode == 1 and ": error: " in diagnostic and not proc.stdout else "process-error"
    return {"status": status, "exit": proc.returncode, "diagnostic": diagnostic}


def probe(row, wheelhouse, builds, timeout):
    module = row["import"]
    names = module.split(".")
    if not all(name.isidentifier() and not keyword.iskeyword(name) for name in names):
        raise ValueError(f"invalid import: {module!r}")
    with tempfile.TemporaryDirectory(prefix="pystachy-import-ir-") as tmp:
        work = Path(tmp)
        site = work / "wheel"
        site.mkdir()
        wheel_source(row, wheelhouse, site)
        base = site.joinpath(*names)
        targets = [p for p in (base.with_suffix(".py"), base / "__init__.py") if p.is_file()]
        if names[0] in sys.stdlib_module_names or len(targets) != 1:
            return row | {"exclusion": "import not uniquely attributable to wheel"}
        target, = targets
        driver = work / "wheel-import.py"
        driver.write_text(f"import {module}\n")
        outcomes = {}
        for label, (compiler, env) in builds.items():
            env = env | {"PYSTACHY_PATH": str(site)}
            result = compile_ir(compiler, env, driver, timeout)
            if result["status"] == "ir":
                # A builtin or another source may win resolution despite an installed wheel file.
                # Require the same import to reach the pinned target; restore it before the next build.
                original = target.read_bytes()
                try:
                    target.write_bytes(b"if :\n")
                    control = compile_ir(compiler, env, driver, timeout)
                finally:
                    target.write_bytes(original)
                expected = f"WHEEL/{target.relative_to(site).as_posix()}:1: error: invalid syntax"
                if control != {"status": "rejected", "exit": 1, "diagnostic": expected}:
                    result = {"status": "unattributed", "control": control}
            outcomes[label] = result
        return row | {"outcomes": outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cohort", type=Path)
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("roots", nargs="+", metavar="LABEL=CHECKOUT")
    parser.add_argument("-j", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()
    if args.j < 1 or args.timeout < 1 or args.cohort.resolve() == args.results.resolve():
        parser.error("use positive worker/time limits and a distinct output path")
    if sys.version.split()[0] != (Path(__file__).resolve().parents[1] / ".python-version").read_text().strip():
        parser.error("use the repository's pinned CPython")
    data = args.cohort.read_bytes()
    rows = [json.loads(line) for line in data.splitlines()]
    if not rows or len({r["rank"] for r in rows}) != len(rows):
        parser.error("cohort is empty or repeats a rank")
    builds, identities = {}, {}
    env = {k: os.environ[k] for k in ("PATH", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "SDKROOT", "PYSTACHY_LLVM")
           if k in os.environ}
    with tempfile.TemporaryDirectory(prefix="pystachy-import-caches-") as tmp:
        for index, spec in enumerate(args.roots):
            label, sep, path = spec.partition("=")
            if not sep or not path or not label or label in builds:
                parser.error(f"invalid or duplicate compiler: {spec!r}")
            root = Path(path).resolve()
            compiler = root / "pystachy"
            if not compiler.is_file() or not (root / "runtime.c").is_file():
                parser.error(f"expected native ./pystachy and runtime.c in {root}")
            cache = Path(tmp) / str(index)
            cache.mkdir()
            builds[label] = (compiler, env | {"PYSTACHY_HOME": str(root), "PYSTACHY_CACHE": str(cache), "LC_ALL": "C"})
            identities[label] = {"source": source_git(root), "binary_sha256": compiler_sha256(compiler),
                                 "tree": subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD^{tree}"], text=True).strip()}
        with ThreadPoolExecutor(args.j) as pool:
            results = list(pool.map(lambda row: probe(row, args.wheelhouse, builds, args.timeout), rows))
    report = {"cohort_sha256": hashlib.sha256(data).hexdigest(), "python": sys.version.split()[0],
              "compilers": identities, "timeout_s": args.timeout, "rows": sorted(results, key=lambda r: r["rank"])}
    args.results.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
