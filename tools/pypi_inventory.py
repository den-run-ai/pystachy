"""Manual PyPI census. Resolve a ranking, scan pinned wheels, or replay a stdlib inventory.

resolve reads a top-pypi-packages JSON snapshot and writes one release per rank.
scan verifies each selected wheel, parses source without importing it, and emits stdlib
profiles. compare measures bare module import IR on both compilers, then scores the
same profiles against each. A profile never establishes package import or execution.
"""
import argparse
import ast
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import sysconfig
import tempfile
import urllib.error
import urllib.request
import warnings
import zipfile

import import_sweep

MAX_WHEEL = 50_000_000
MAX_SOURCE = 3_000_000
SKIP = {"test", "tests", "testing", "docs", "doc", "examples", "example", "benchmarks", "__pycache__"}


def pure_release(files):
    live = [f for f in files if not f["yanked"]]
    wheels = [f for f in live if f["packagetype"] == "bdist_wheel"]
    for f in sorted(wheels, key=lambda file: file["filename"]):
        name = f["filename"]
        if name.endswith("-none-any.whl") and any(tag.startswith("py3") for tag in name.split("-")[-3].split(".")):
            return {"status": "pure-wheel", "filename": name, "url": f["url"], "sha256": f["digests"]["sha256"],
                    "size": f["size"]}
    if wheels:
        return {"status": "no-eligible-pure-wheel"}
    if any(f["packagetype"] == "sdist" for f in live):
        return {"status": "sdist-only"}
    return {"status": "no-files"}


def resolve(row):
    rank, name = row
    result = {"rank": rank, "project": name}
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=45) as response:
            release = json.load(response)
    except urllib.error.HTTPError as error:
        return result | {"status": "missing" if error.code == 404 else "fetch-error", "error": str(error)}
    except (OSError, ValueError) as error:
        return result | {"status": "fetch-error", "error": str(error)}
    return result | {"version": release["info"]["version"], "requires_python": release["info"].get("requires_python"),
                     "requires_dist": release["info"].get("requires_dist")} | pure_release(release["urls"])


def dependencies(body, known_roots):
    # Recovered inventory policy: module suites, excluding optional imports and TYPE_CHECKING.
    found = set()
    for node in body:
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{a.name}" for a in node.names if a.name != "*")
        elif isinstance(node, ast.Try):
            if not import_sweep.fallback(node):
                found.update(dependencies(node.body, known_roots))
            for handler in node.handlers:
                found.update(dependencies(handler.body, known_roots))
            found.update(dependencies(node.orelse + node.finalbody, known_roots))
        elif isinstance(node, ast.If):
            tc = ((isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING") or
                  (isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING"))
            if not tc:
                found.update(dependencies(node.body, known_roots))
            found.update(dependencies(node.orelse, known_roots))
        elif isinstance(node, ast.With):
            found.update(dependencies(node.body, known_roots))
    return {name for name in found if name.split(".")[0] in known_roots}


def wheel_profile(data):
    found = set()
    parsed = skipped = 0
    with zipfile.ZipFile(io.BytesIO(data)) as wheel, warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        for member in wheel.infolist():
            parts = member.filename.split("/")
            if parts[0].endswith(".data") and parts[1:2] in (["purelib"], ["platlib"]):
                parts = parts[2:]
            if not parts[-1].endswith(".py") or parts[0].endswith((".dist-info", ".data")) or SKIP.intersection(parts[:-1]):
                continue
            if member.file_size > MAX_SOURCE:
                skipped += 1
                continue
            try:
                tree = ast.parse(wheel.read(member))
                found.update(dependencies(tree.body, sys.stdlib_module_names))
            except (SyntaxError, ValueError, RecursionError):
                skipped += 1
            else:
                parsed += 1
    return {"stdlib": sorted(found), "parsed": parsed, "skipped": skipped}


def scan(row, wheel_dir):
    result = {k: row[k] for k in ("rank", "project", "version") if k in row}
    if row["status"] != "pure-wheel":
        return result | {"status": row["status"]}
    if row["size"] > MAX_WHEEL:
        return result | {"status": "over-size"}
    filename = row["filename"]
    if Path(filename).name != filename:
        raise ValueError(f"invalid wheel filename: {filename!r}")
    result["sha256"] = row["sha256"]
    try:
        path = wheel_dir / filename if wheel_dir else None
        if path and path.is_file():
            with path.open("rb") as source:
                data = source.read(MAX_WHEEL + 1)
        else:
            with urllib.request.urlopen(row["url"], timeout=45) as response:
                data = response.read(MAX_WHEEL + 1)
        if len(data) != row["size"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            return result | {"status": "integrity-error"}
        profile = wheel_profile(data)
    except (OSError, zipfile.BadZipFile, ValueError) as error:
        return result | {"status": "scan-error", "error": str(error)}
    if not profile["parsed"]:
        status = "no-parseable-source" if profile["skipped"] else "no-source"
    else:
        status = "partial" if profile["skipped"] else "scanned"
    return result | {"status": status} | profile


def known_modules(rows):
    # Include platform builtins and actual submodule files, without importing package initializers.
    known = set(sys.stdlib_module_names) | {"os.path"}
    lib = Path(sysconfig.get_path("stdlib"))
    candidates = set().union(*(r.get("stdlib", []) for r in rows))
    for name in candidates:
        parts = name.split(".")
        if parts[0] not in sys.stdlib_module_names or not all(part.isidentifier() for part in parts):
            continue
        while name and name not in known:
            path = lib.joinpath(*name.split("."))
            if path.with_suffix(".py").is_file() or (path / "__init__.py").is_file():
                known.add(name)
            name = name.rpartition(".")[0]
    return known


def profile_modules(names, known):
    # The archive includes possible submodule names for from-imports (e.g. json.dumps).
    # Use the longest known module prefix, resolved against the same CPython for both compilers.
    required = set()
    for name in names:
        while name and name not in known:
            name = name.rpartition(".")[0]
        if name:
            required.add(name)
    return required


def module_ir(compiler, modules, workers, timeout):
    compiler = Path(compiler).resolve()
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    home = compiler.parent
    if not (home / "runtime.c").is_file() and (home.parent / "runtime.c").is_file():
        home = home.parent
    if not compiler.is_file() or not (home / "runtime.c").is_file():
        raise ValueError(f"expected a Pystachy build with its runtime: {compiler}")
    env["PYSTACHY_HOME"] = str(home)
    with tempfile.TemporaryDirectory() as tmp:
        env["PYSTACHY_CACHE"] = str(Path(tmp) / "cache")
        def run(name):
            with tempfile.TemporaryDirectory(dir=tmp) as wd:
                status, _ = import_sweep.compile_one([str(compiler)], env, wd, name, timeout, False)
                return name, status.replace(wd, "PROBE").replace(str(home), "COMPILER")
        with concurrent.futures.ThreadPoolExecutor(workers) as pool:
            results = dict(pool.map(run, sorted(modules)))
    return {"sha256": import_sweep.compiler_sha256(compiler),
            "source": import_sweep.source_git(home), "modules": results}


def compare(rows, before, after, workers, timeout):
    known = known_modules(rows)
    required = [profile_modules(r.get("stdlib", []), known) for r in rows]
    names = set().union(*required)
    old = module_ir(before, names, workers, timeout)
    new = module_ir(after, names, workers, timeout)
    projects = []
    for row, deps in zip(rows, required, strict=True):
        item = {k: row[k] for k in ("rank", "project", "version", "sha256", "status", "parsed", "skipped", "profile_source") if k in row}
        if "stdlib" in row and row.get("parsed", bool(row["stdlib"])) > 0:
            for key, report in (("before", old), ("after", new)):
                item[key] = sorted(m for m in deps if report["modules"][m] != "OK")
            item["required_count"] = len(deps)
        projects.append(item)
    return {"python": sys.version, "timeout_seconds": timeout, "workers": workers,
            "before": old, "after": new, "projects": projects}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for name, help_text in (("resolve", "ranked JSON to release manifest"),
                            ("scan", "release manifest to stdlib inventory"),
                            ("compare", "score the same inventory on two compiler builds")):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("input", type=Path)
        sub.add_argument("output", type=Path)
        sub.add_argument("-j", type=int, default=2)
        if name in ("resolve", "scan"):
            sub.add_argument("--limit", type=int, default=10_000, help="first N ranks")
        if name == "scan":
            sub.add_argument("--wheel-dir", type=Path, help="reuse local wheel files after checking their hashes")
        if name == "compare":
            sub.add_argument("before", type=Path)
            sub.add_argument("after", type=Path)
            sub.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if args.j <= 0 or getattr(args, "limit", 1) <= 0 or getattr(args, "timeout", 1) <= 0:
        parser.error("workers, rank limit and timeout must be positive")
    if args.output.resolve() == args.input.resolve():
        parser.error("input and output must differ")
    rows = json.loads(args.input.read_bytes())
    if args.action != "resolve":
        for row in rows:
            if row.get("status") == "binary-only":  # original resolver included Python 2 pure wheels here
                row["status"] = "no-eligible-pure-wheel"
    if args.action == "compare":
        result = compare(rows, args.before, args.after, args.j, args.timeout)
        result["input_sha256"] = import_sweep.compiler_sha256(args.input)
    else:
        with concurrent.futures.ThreadPoolExecutor(args.j) as pool:
            if args.action == "resolve":
                names = [r["project"] for r in rows["rows"][:args.limit]]
                result = list(pool.map(resolve, enumerate(names, 1)))
            else:
                selected = [r for r in rows if r["rank"] <= args.limit]
                result = list(pool.map(lambda row: scan(row, args.wheel_dir), selected))
    args.output.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
