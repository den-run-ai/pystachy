"""Exact hosted output checks for the isolated lowering-memory candidates.

The baseline replaces only Gen.lower/Gen.lower_module with their actual source at
the reference commit. Every other compiler file must match the reference. Each
case runs in a fresh interpreter to isolate the compiler's module-level state.
This is a correctness check, not a timing benchmark.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys


BASE = "fa9bba371c792999b6161b8aa507e8c584b1b0f5"
SOURCES = {
    "lowering": ("gen_lower", "lower"),
    "lower_module": ("gen_lower_module", "lower_module"),
}
FIXTURES = (
    "tests/programs/generators/gen_finally.py",
    "tests/programs/generators/gen_cm_gc.py",
    "tests/programs/language/recursion_closed.py",
    "tests/programs/containers/tuple_return_values.py",
    "tests/programs/containers/tuple_return_closures.py",
    "tests/programs/inference/dynany_identity_list_scalar_reads.py",
)
EXTENSION = '''from ffi import export

def _pair(x: int) -> tuple[int, int]:
    return x + 1, x + 2

@export
def value(x: int) -> int:
    a, b = _pair(x)
    return a + b

@export
def text(s: str) -> str:
    try:
        if s == "":
            raise ValueError("empty")
        return s + "!"
    except ValueError:
        return "caught"
'''


def cases(root: Path) -> list[dict]:
    result = []
    for opt in ("", "-all"):
        for name, source in (("empty", ""), ("tiny", "print(1)\n"),
                             ("extension", EXTENSION)):
            result.append({"name": name, "source": source, "path": name + ".py",
                           "mode": "extension" if name == "extension" else "program",
                           "opt": opt})
        for name in FIXTURES:
            result.append({"name": Path(name).stem, "source": (root / name).read_text(),
                           "path": str(root / name), "mode": "program", "opt": opt})
        result.append({"name": "runtime", "source": (root / "runtime.py").read_text(),
                       "path": str(root / "runtime.py"), "mode": "runtime", "opt": opt})
    return result


def reference(root: Path, relative: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{BASE}:{relative}"], cwd=root)


def child(args: argparse.Namespace) -> None:
    root = args.root
    sys.path.insert(0, str(root))
    from src.pystachy_compiler.driver import compile_program, runtime_ir
    from src.pystachy_compiler.gen import Gen
    if args.policy == "baseline":
        for name, (function, method) in SOURCES.items():
            relative = f"src/pystachy_compiler/{name}.py"
            module = importlib.import_module(f"src.pystachy_compiler.{name}")
            node = next(n for n in ast.parse(reference(root, relative)).body
                        if isinstance(n, ast.FunctionDef) and n.name == function)
            namespace = module.__dict__.copy()
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         f"{BASE}:{relative}", "exec"), namespace)
            setattr(Gen, method, namespace[function])
    case = cases(root)[args.child]
    os.environ["PYSTACHY_OPT"] = case["opt"]
    if case["mode"] == "runtime":
        output = runtime_ir(case["path"], case["source"], False)
    else:
        output = compile_program(case["path"], case["source"], [str(root / "lib")],
                                 "probe" if case["mode"] == "extension" else "")
    sys.stdout.write(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", type=int)
    parser.add_argument("--policy", choices=("baseline", "candidate"))
    args = parser.parse_args()
    args.root = args.root.resolve()
    if args.child is not None:
        child(args)
        return
    if args.output is None:
        parser.error("--output is required")
    args.output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for path in sorted((args.root / "src").rglob("*.py")):
        relative = str(path.relative_to(args.root))
        content = path.read_bytes()
        hashes[relative] = hashlib.sha256(content).hexdigest()
        if path.stem not in SOURCES:
            original = reference(args.root, relative)
            if original != content and ast.dump(ast.parse(original)) != ast.dump(ast.parse(content)):
                raise RuntimeError(f"uncontrolled compiler change: {relative}")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    environment.update(PYTHONHASHSEED="0", PYSTACHY_IRCHECK="1")
    records = []
    for index, case in enumerate(cases(args.root)):
        samples = {}
        for policy in ("baseline", "candidate"):
            stem = f"{index:02d}-{case['name']}-{policy}"
            output = args.output / (stem + ".ll")
            diagnostics = args.output / (stem + ".err")
            command = [sys.executable, str(Path(__file__).resolve()), "--root", str(args.root),
                       "--child", str(index), "--policy", policy]
            with output.open("wb") as out, diagnostics.open("wb") as err:
                run = subprocess.run(command, stdout=out, stderr=err, cwd=args.root,
                                     env=environment, timeout=30)
            data = output.read_bytes()
            samples[policy] = {"status": run.returncode, "bytes": len(data),
                               "ir_sha256": hashlib.sha256(data).hexdigest(),
                               "stderr_sha256": hashlib.sha256(diagnostics.read_bytes()).hexdigest()}
        matches = samples["baseline"] == samples["candidate"] and samples["candidate"]["status"] == 0
        records.append({"case": case["name"], "mode": case["mode"], "opt": case["opt"],
                        "source_sha256": hashlib.sha256(case["source"].encode()).hexdigest(),
                        "matches": matches, **samples})
        print(f"{index + 1:02d} {case['name']} {case['opt'] or 'default'}: {'match' if matches else 'FAIL'}", flush=True)
    report = {"baseline": BASE, "candidate_head": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=args.root, text=True).strip(),
        "compiler_files_sha256": hashes, "python": sys.version, "records": records,
        "matches": sum(row["matches"] for row in records)}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if report["matches"] != len(records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
