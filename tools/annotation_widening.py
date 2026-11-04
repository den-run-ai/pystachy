"""Qualify annotation-only transformations with pinned CPython, then check native JIT/AOT.

Discover a bounded entry-module cohort in the maintained differential corpus. Keep formatting,
integer policy, non-selected annotations, imported modules, fixture paths and sidecars intact.
"""
import argparse
import ast
from collections import Counter
from io import BytesIO
from itertools import product
import json
from pathlib import Path
import shlex
import sys
import tempfile
import tokenize

import dynany_optin as corpus

ROOT = corpus.ROOT
MANIFEST = "tools/annotation_widening_exceptions.json"
SCALARS = {"bool", "int", "float", "str"}
# These programs observe aliasing during allocation under both integer policies.
GC_CASES = {"tests/programs/inference/dynany_identity_call_returns.py",
            "tests/programs/numbers/python_int_any_constants.py"}
NATIVE_LIST_CASE = "tests/programs/inference/dynany_native_int_list.py"
PR_CASES = GC_CASES | {"tests/programs/inference/dynany_identity_call_edges.py"}
MODES = ("jit", "aot")


def bound_name(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler,
                         ast.MatchAs, ast.MatchStar)):
        return node.name
    if isinstance(node, ast.alias):
        return node.asname or node.name.split(".")[0]
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        return node.id
    if isinstance(node, ast.arg):
        return node.arg
    if isinstance(node, ast.MatchMapping):
        return node.rest
    return None


def widen(source):
    """Return (source bytes, widened functions, exclusion reason). Only replace AST name spans."""
    if corpus.opt_in(source) != source:
        return source, [], "entry does not opt into dynamic Any"
    # AST columns are UTF-8 byte offsets (without a BOM). Splice only that encoding.
    encoding, _ = tokenize.detect_encoding(BytesIO(source).readline)
    if encoding != "utf-8":
        return source, [], "non-UTF-8 or BOM entry"
    tree = ast.parse(source)
    nodes = list(ast.walk(tree))
    # Reject ambiguous bindings conservatively, even if a redefinition was in another scope.
    bindings = Counter(bound_name(node) for node in nodes)
    imports = [(alias.asname or alias.name, statement.lineno) for statement in tree.body
               if isinstance(statement, ast.ImportFrom) and statement.level == 0 and statement.module == "typing"
               for alias in statement.names if alias.name == "Any" and bindings[bound_name(alias)] == 1]
    if not imports or bindings["*"]:
        return source, [], "no unambiguous explicit typing.Any import"
    observed = {"__annotations__", "get_annotations", "get_type_hints", "signature", "globals", "eval", "exec"}
    if any(isinstance(node, ast.Name) and node.id in observed or
           isinstance(node, ast.Attribute) and node.attr in observed or
           isinstance(node, ast.alias) and node.name in observed for node in nodes):
        return source, [], "runtime annotation or namespace inspection"
    references = Counter(node.id for node in nodes if isinstance(node, ast.Name))
    calls = Counter(node.func.id for node in nodes if isinstance(node, ast.Call) and isinstance(node.func, ast.Name))
    edits, functions = [], []
    for fn in tree.body:
        # No classes, decorators, generic/ABI signatures, generator channels, variable
        # annotations, or exported callbacks. Each eligible body is a single non-generator return.
        if not isinstance(fn, ast.FunctionDef) or fn.decorator_list or getattr(fn, "type_params", ()):
            continue
        if (len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return) or
                any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(fn.body[0]))):
            continue
        if bindings[fn.name] != 1 or not calls[fn.name] or calls[fn.name] != references[fn.name]:
            continue
        args = fn.args
        if not args.args or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg:
            continue
        name = next((name for name, line in imports if line < fn.lineno), None)
        if name is None:
            continue
        annotations = [a.annotation for a in args.args] + [fn.returns]
        if not all(isinstance(a, ast.Name) and a.id in SCALARS and not bindings[a.id] for a in annotations):
            # The native-list boundary keeps the return type Any; widen the parameter only.
            if (len(annotations) != 2 or not isinstance(fn.returns, ast.Name) or fn.returns.id != name or
                    not isinstance(annotations[0], ast.Subscript) or
                    not isinstance(annotations[0].value, ast.Name) or annotations[0].value.id != "list" or
                    not isinstance(annotations[0].slice, ast.Name) or annotations[0].slice.id != "int" or
                    bindings["int"] or bindings["list"] or annotations[0].lineno != annotations[0].end_lineno):
                continue
            annotations = annotations[:1]
        for a in annotations:
            edits.append((a.lineno - 1, a.col_offset, a.end_col_offset, name.encode()))
        functions.append(fn.name)
    lines = source.splitlines(keepends=True)
    for line, start, end, replacement in sorted(edits, reverse=True):
        lines[line] = lines[line][:start] + replacement + lines[line][end:]
    return b"".join(lines), functions, "" if functions else "no eligible direct scalar signature"


def discover(root):
    candidates, excluded = {}, Counter()
    for case in corpus.programs(root):
        source, functions, reason = widen((root / case).read_bytes())
        if functions:
            candidates[case] = (source, functions)
        else:
            excluded[reason] += 1
    required = set(PR_CASES)
    if (root / NATIVE_LIST_CASE).exists():
        required.add(NATIVE_LIST_CASE)
    if not required <= candidates.keys():
        raise ValueError(f"required widening cases no longer eligible: {sorted(required - candidates.keys())}")
    return candidates, excluded


def record(tree, case, env, timeout):
    path = (tree / case).with_suffix(".out")
    path.unlink(missing_ok=True)
    path.with_suffix(".err").unlink(missing_ok=True)
    status, output = corpus.run(["sh", "tests/record.sh", case], tree, env, timeout)
    if not corpus.recorded(status, output, case, tree):
        raise ValueError(f"{case}: CPython recording failed: {output!r}")
    if path.with_suffix(".err").exists() or not path.read_bytes().endswith(b"[exit 0]\n"):
        raise ValueError(f"{case}: strict widening cohort requires successful CPython execution with empty stderr")
    return path.read_bytes()


def lanes(case):
    stress = (False, True) if case in GC_CASES or case == NATIVE_LIST_CASE else (False,)
    return product(("original", "widened"), stress, MODES)


def execute(case, widened, trees, temp, compiler, allowed, timeout):
    original, changed = trees
    env = corpus.environment(ROOT, temp)
    for tree in trees:
        case_path = tree / case
        if case_path.resolve() != tree.resolve() / case:
            raise ValueError(f"{case}: symlink in temporary corpus path")
    path = changed / case
    path.write_bytes(widened)
    try:
        # Re-record both before invoking the compiler. An observable annotation change is not
        # evidence of parity; fail a newly discovered one so it receives an explicit exclusion.
        baseline = record(original, case, env, timeout)
        variant = record(changed, case, env, timeout)
        if baseline != variant:
            raise ValueError(f"{case}: excluded from parity: widening changed CPython output")
        if not corpus.recording_unchanged(case, ROOT, original):
            raise ValueError(f"{case}: original CPython recording drifted")
        rows = []
        for form, stress, mode in lanes(case):
            tree = original if form == "original" else changed
            env["PYSTACHY_GC_STRESS_PROGRAM"] = "1" if stress else "0"
            exception = allowed.get((case, mode)) if form == "widened" else None
            cmd, trace = (corpus.rejection_wrapper(compiler, case, mode, temp)
                          if exception else (compiler, None))
            status, output = corpus.run(["sh", "tests/run.sh", cmd, mode, case], tree, env, timeout)
            ok, diagnostic = corpus.harness_result(status, output, case)
            result = corpus.classify(ok, diagnostic, exception, corpus.rejection_status(trace, diagnostic))
            if result == "fail":
                detail = diagnostic if not ok else "unexpected pass; retire the exception"
                print(f"FAIL {case} {form} {mode} GC={stress}: {detail}", flush=True)
            rows.append({"form": form, "mode": mode, "gc": stress, "result": result, "diagnostic": diagnostic})
        return rows
    finally:
        # Other cases may import this entry as a support module. Only the current entry is widened.
        path.write_bytes((original / case).read_bytes())


def selected_cases(candidates, profile, index=0, count=1):
    chosen = (PR_CASES | {NATIVE_LIST_CASE}) & candidates.keys() if profile == "pr" else candidates
    return sorted(chosen)[index::count]


def expected_ci_report(root, profile):
    candidates, excluded = discover(root)
    selected = selected_cases(candidates, profile)
    allowed = corpus.exceptions(root, list(candidates), MANIFEST)
    cases = []
    for case in selected:
        rows = []
        for form, stress, mode in lanes(case):
            exception = allowed.get((case, mode)) if form == "widened" else None
            rows.append({"form": form, "mode": mode, "gc": stress,
                         "result": "expected-failure" if exception else "pass",
                         "diagnostic": exception["diagnostic"] if exception else ""})
        cases.append({"case": case, "functions": candidates[case][1], "results": rows})
    return {"profile": profile, "eligible": len(candidates), "excluded": dict(excluded),
            "corpus_sha256": corpus.corpus_digest(root, selected), "python": (root / ".python-version").read_text().strip(),
            "selected": selected, "shard_index": 0, "shard_count": 1, "cases": cases, "failures": []}


def validate_report(report, root, profile):
    # Strict JSON comparison also distinguishes false from 0 and true from 1.
    if json.dumps(report, sort_keys=True) != json.dumps(expected_ci_report(root, profile), sort_keys=True):
        raise ValueError("incomplete or changed annotation-widening evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="./pystachy")
    parser.add_argument("--profile", choices=("pr", "full"), default="full")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.shard_index < args.shard_count:
        parser.error("invalid shard")
    if sys.implementation.name != "cpython" or sys.version.split()[0] != (ROOT / ".python-version").read_text().strip():
        parser.error("run with the exact CPython version pinned by .python-version")
    candidates, excluded = discover(ROOT)
    allowed = corpus.exceptions(ROOT, list(candidates), MANIFEST)
    selected = selected_cases(candidates, args.profile, args.shard_index, args.shard_count)
    if not selected:
        parser.error("empty widening shard")
    compiler = shlex.join([str((ROOT / word).resolve()) if (ROOT / word).is_file() else word
                           for word in shlex.split(args.compiler)])
    digest = corpus.corpus_digest(ROOT, selected)
    cases, failures = [], []
    with tempfile.TemporaryDirectory(prefix="pystachy-widen-") as tmp:
        work = Path(tmp)
        trees = (work / "original", work / "widened")
        for tree in trees:
            corpus.prepare_tree(ROOT, tree, [])
        for case in selected:
            temp = work / Path(case).stem
            temp.mkdir()
            source, functions = candidates[case]
            try:
                rows = execute(case, source, trees, temp, compiler, allowed, 90)
                if any(row["result"] == "fail" for row in rows):
                    failures.append(case)
                cases.append({"case": case, "functions": functions, "results": rows})
            except ValueError as error:
                failures.append(str(error))
                print(f"FAIL {error}", flush=True)
    report = {"profile": args.profile, "eligible": len(candidates), "excluded": dict(excluded),
              "corpus_sha256": digest, "python": sys.version.split()[0],
              "selected": selected, "shard_index": args.shard_index, "shard_count": args.shard_count,
              "cases": cases, "failures": failures}
    if not failures and args.shard_count == 1:
        validate_report(report, ROOT, args.profile)
    if args.report:
        args.report.write_text(json.dumps(report, separators=(",", ":")) + "\n")
    print(f"{len(candidates)} eligible, excluded {dict(excluded)}; {len(cases)}/{len(selected)} CPython-qualified; "
          f"{sum(len(case['results']) for case in cases)} native checks, {len(failures)} failures")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
