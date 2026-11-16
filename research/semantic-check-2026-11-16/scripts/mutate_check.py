"""Mutation harness for pystachy check's unit recovery.

usage: python3 -I mutate_check.py COMPILER OUTDIR PROGRAM...

For each program that `ir` compiles, inject `__pys_bad = 1 + "injected"` as the first statement
(after a docstring) of one function, and then of two functions, and run `check`. Every `error:`
line `check` reports must be at an injected line; the first line must equal `ir`'s message.
Notes (units whose types may depend on a body left out) are allowed anywhere.
"""
import ast
import concurrent.futures
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

INJECT = 'pys_bad_injected = 1 + "injected"'
ERROR = re.compile(r"^(.*?):(\d+): error: ")


def functions(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []
    def visit(body, depth):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and depth < 2:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and isinstance(first.value.value, str):
                    if len(node.body) < 2:
                        continue
                    first = node.body[1]
                if first.lineno == node.lineno:
                    continue
                out.append((first.lineno, first.col_offset, node.name))
            elif isinstance(node, ast.ClassDef) and depth == 0:
                visit(node.body, depth + 1)
    visit(tree.body, 0)
    return out


def inject(lines, sites):
    # sites: (line, column) to insert before; returns the new text and the injected line numbers
    out = list(lines)
    injected = []
    for line, col, _ in sorted(sites, reverse=True):
        out.insert(line - 1, " " * col + INJECT + "\n")
    shift = 0
    for line, col, _ in sorted(sites):
        injected.append(line + shift)
        shift += 1
    return "".join(out), injected


def run(cmd, path, mp):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = os.environ.get("PYSTACHY_HOME", "")
    if mp:
        env["PYSTACHY_PATH"] = mp
    r = subprocess.run(cmd + [str(path)], capture_output=True, text=True, errors="replace", env=env, timeout=600)
    return r.returncode, r.stderr


def one(compiler, program, work):
    src = Path(program).read_text(encoding="latin-1")
    sites = functions(src)
    if not sites:
        return []
    mp = ""
    pathfile = Path(program[:-3] + ".path")
    if pathfile.exists():
        return []  # (import-path cases need tests/prepare_path.sh; left out)
    lines = src.splitlines(True)
    picks = [[sites[0]]]
    if len(sites) > 1:
        picks.append([sites[0], sites[-1]])
    results = []
    for k, chosen in enumerate(picks):
        text, injected = inject(lines, chosen)
        # (each injected line must be a statement of a function body, as CPython parses it)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        placed = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for st in node.body:
                    if isinstance(st, ast.Assign) and st.lineno in injected and isinstance(st.targets[0], ast.Name) and st.targets[0].id == "pys_bad_injected":
                        placed.add(st.lineno)
        if placed != set(injected):
            continue
        d = Path(tempfile.mkdtemp(dir=work))
        target = d / Path(program).name
        target.write_text(text, encoding="latin-1")
        # helper modules beside the program stay importable: link the program's directory's files
        for sibling in Path(program).parent.iterdir():
            if sibling.name != target.name and not (d / sibling.name).exists():
                os.symlink(sibling.resolve(), d / sibling.name)
        a, ir_err = run(compiler + ["ir"], target, mp)
        b, chk = run(compiler + ["check"], target, mp)
        errors = [m for m in (ERROR.match(l) for l in chk.splitlines()) if m]
        bad = [m.group(0) for m in errors if not (m.group(1) == str(target) and int(m.group(2)) in injected)]
        first_ok = (a == 0 and b == 0 and chk == "") or (a == b == 1 and chk.splitlines()[:1] == ir_err.splitlines()[:1])
        results.append({"program": program, "functions": [c[2] for c in chosen], "injected": injected,
                        "ir": a, "check": b, "errors": len(errors),
                        "notes": len([l for l in chk.splitlines() if ": note: " in l]),
                        "invented": bad, "first_matches_ir": first_ok,
                        "stopped": "checking stopped" in chk,
                        "output": chk.replace(str(d) + "/", "")[:2000]})
    return results


def main():
    compiler = sys.argv[1].split()
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    programs = sys.argv[3:]
    work = Path(tempfile.mkdtemp(prefix="mutate-check-"))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get("JOBS", "4"))) as pool:
        for r in pool.map(lambda p: one(compiler, p, str(work)), programs):
            results.extend(r)
    (out / "mutations.json").write_text(json.dumps(results, indent=1))
    invented = [r for r in results if r["invented"]]
    mismatched = [r for r in results if not r["first_matches_ir"]]
    print(json.dumps({"mutants": len(results), "programs": len({r["program"] for r in results}),
                      "rejected_by_ir": len([r for r in results if r["ir"] == 1]),
                      "errors_reported": sum(r["errors"] for r in results),
                      "two_errors_found": len([r for r in results if len(r["injected"]) == 2 and r["errors"] == 2]),
                      "two_site_mutants": len([r for r in results if len(r["injected"]) == 2]),
                      "with_notes": len([r for r in results if r["notes"] > 0]),
                      "stopped": len([r for r in results if r["stopped"]]),
                      "invented": len(invented), "first_line_mismatch": len(mismatched)}, indent=1))
    for r in (invented + mismatched)[:10]:
        print("PROBLEM", r["program"], r["functions"], r["invented"] or "first line differs from ir")
        print("   ", r["output"][:600].replace("\n", "\n    "))
    return 1 if invented or mismatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
