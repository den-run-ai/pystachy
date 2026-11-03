#!/usr/bin/env python3
"""Deterministic, lightweight PR sample; full native/release verification stays exhaustive.

Use the exact tests/corpus.sh inventory, two inexpensive representatives per program
area (and deviations), one per rejection area, named safety regressions and every
special test-driver path. Changed cases/sidecars are added without a size cap: a
large PR must not silently lose its new tests to keep the ordinary sample small.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SELECTOR = "area-smoke-v1"
# These exercise allocator roots, object lifetimes, optimizer effects, import paths,
# integer representations and generators even when cheaper area cases are errors.
SMOKE_CASES = (
    "tests/programs/runtime/gc_churn.py",
    "tests/programs/runtime/gc_dict_values.py",
    "tests/programs/runtime/gc_list_kinds.py",
    "tests/programs/runtime/gc_template_empty_kind.py",
    "tests/programs/containers/tuple_runtime_lifetime.py",
    "tests/programs/containers/dict_changed_size.py",
    "tests/programs/language/closures.py",
    "tests/programs/language/closure_paths.py",
    "tests/programs/language/ffi_own.py",
    "tests/programs/numbers/arith.py",
    "tests/programs/numbers/mpz_arithmetic.py",
    "tests/programs/numbers/python_int_exit.py",
    "tests/programs/generators/gen_basic.py",
    "tests/programs/generators/gen_close.py",
    "tests/programs/optimizations/fold_effects.py",
    "tests/programs/optimizations/opt_loops.py",
    "tests/programs/strings/bytes_core.py",
    "tests/programs/inference/dynany_identity_expression_lifetime.py",
    "tests/programs/library/lib_select_sigint.py",
)
SIDECARS = frozenset((".py", ".out", ".err", ".in", ".full", ".path"))


def corpus(root=ROOT):
    """Return the authoritative corpus in its C-locale order, without re-globbing."""
    result = subprocess.run(
        ["sh", "-c", ". tests/corpus.sh; corpus"], cwd=root,
        env={**os.environ, "LC_ALL": "C"}, text=True, capture_output=True,
        check=True, timeout=30)
    cases = result.stdout.splitlines()
    if not cases or len(set(cases)) != len(cases):
        raise ValueError("PR sample needs a nonempty, unique corpus")
    for name in cases:
        path = Path(name)
        parts = path.parts
        valid = (len(parts) == 4 and parts[:2] in (("tests", "programs"), ("tests", "errors")) or
                 len(parts) == 3 and parts[:2] == ("tests", "deviations"))
        if not valid or path.suffix != ".py" or not (root / path).is_file():
            raise ValueError(f"unexpected corpus case: {name}")
    return cases


def case_weights(root, cases):
    """Read corpus.sh's advisory costs; malformed/stale weights never remove a case."""
    defaults = {"program": 1000, "rejection": 1000}
    measured = {}
    table = root / "tests/case_weights.txt"
    for line in table.read_text().splitlines() if table.exists() else ():
        fields = line.split()
        if len(fields) == 3 and fields[0] == "default" and fields[1] in defaults:
            if re.fullmatch(r"[0-9]{1,9}", fields[2]):
                defaults[fields[1]] = int(fields[2])
        elif len(fields) == 2 and re.fullmatch(r"[0-9]{1,9}", fields[0]):
            measured[fields[1]] = int(fields[0])
    return {name: measured.get(name, defaults["rejection" if name.startswith("tests/errors/")
                                              else "program"]) for name in cases}


def resolve_base(root, base):
    if base is None:
        return None
    if not isinstance(base, str) or not base.strip():
        raise ValueError("the supplied PR base must name a commit")
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", base + "^{commit}"],
        cwd=root, text=True, capture_output=True, timeout=30)
    commit = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ValueError(f"cannot resolve PR base commit {base!r}; fetch that commit first")
    return commit


def changed_cases(root, cases, base_commit):
    """Include changed fixtures, new local cases, and direct helper-package consumers."""
    if base_commit is None:
        return set()
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "-z", base_commit, "--", "tests"],
        cwd=root, capture_output=True, check=True, timeout=30).stdout
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", "tests"],
        cwd=root, capture_output=True, check=True, timeout=30).stdout
    changed = {os.fsdecode(name) for name in (tracked + untracked).split(b"\0") if name}
    present = set(cases)
    selected = set()
    helpers = set()
    for name in changed:
        path = Path(name)
        if path.suffix in SIDECARS and str(path.with_suffix(".py")) in present:
            selected.add(str(path.with_suffix(".py")))
        elif len(path.parts) >= 2 and path.parts[0] == "tests" and path.suffix == ".py":
            if path.parts[1] not in ("programs", "errors", "deviations"):
                helpers.add(path.parts[1].removesuffix(".py"))
    if helpers:
        # .path commonly names tests/; only consumers importing the changed module
        # need additional cases. Match import statements also in rejection fixtures
        # that deliberately cannot be parsed with ast.parse().
        imports = re.compile(r"(?m)^\s*(?:from|import)\s+(" +
                             "|".join(re.escape(name) for name in sorted(helpers)) + r")(?:[.\s,]|$)")
        for name in cases:
            path = root / name
            if path.with_suffix(".path").is_file() and imports.search(path.read_text()):
                selected.add(name)
    return selected


def _selection(root, base):
    root = Path(root)
    cases = corpus(root)
    weights = case_weights(root, cases)
    selected = set(SMOKE_CASES).intersection(cases)
    areas = defaultdict(list)
    for name in cases:
        areas[str(Path(name).parent)].append(name)
    for area, members in areas.items():
        ordered = sorted(members, key=lambda name: (weights[name], name))
        count = 1 if area.startswith("tests/errors/") else 2
        # Prefer different filename families among similarly cheap cases (e.g.
        # property and dataclass). Never select an expensive suite just for its
        # filename; absent measurements use corpus.sh's conservative defaults.
        budget = max(1000, weights[ordered[0]] * 2)
        affordable = [name for name in ordered if weights[name] <= budget]
        families = set()
        representatives = []
        for name in affordable:
            family = Path(name).stem.split("_", 1)[0]
            if family not in families:
                representatives.append(name)
                families.add(family)
                if len(representatives) == count:
                    break
        representatives.extend(name for name in ordered if name not in representatives)
        selected.update(representatives[:count])
    strata = defaultdict(list)
    for name in cases:
        path = root / name
        data = path.read_bytes()
        program = name.startswith("tests/programs/")
        for suffix in (".in", ".path", ".full"):
            if path.with_suffix(suffix).is_file():
                strata[("program" if program else "rejection", suffix)].append(name)
        if program and (b"kill -INT" in data or b"KeyboardInterrupt" in data):
            strata["signal"].append(name)
        if program and re.search(rb"(?m)^(?:import|from) ffi(?:[.\s,]|$)", data):
            strata["ffi"].append(name)
        if path.name.startswith("syntax_"):
            if program:
                strata["syntax-program"].append(name)
            elif name.startswith("tests/errors/") and data.startswith(
                    f"# error: {path.name}:".encode()):
                strata["syntax-rejection"].append(name)
    selected.update(min(members, key=lambda name: (weights[name], name))
                    for members in strata.values())
    base_commit = resolve_base(root, base)
    selected.update(changed_cases(root, cases, base_commit))
    result = [name for name in cases if name in selected]
    if not result:
        raise ValueError("PR selection is empty")
    return result, base_commit


def select_cases(root=ROOT, base=None):
    """Return selected corpus-relative names; a supplied bad base is always fatal."""
    return _selection(root, base)[0]


def manifest(root=ROOT, base=None):
    cases, base_commit = _selection(root, base)
    return {"schema": 1, "profile": "pr", "selector": SELECTOR, "base_commit": base_commit,
            "cases": cases, "cases_sha256": hashlib.sha256(("\n".join(cases) + "\n").encode()).hexdigest()}


def expected_checks(cases, modes=("jit", "aot"), root=ROOT):
    """Mirror tests/run.sh's program, rejection and syntax-check accounting."""
    if not cases or len(set(cases)) != len(cases):
        raise ValueError("expected check count needs nonempty, unique cases")
    if not modes or any(mode not in ("jit", "aot") for mode in modes):
        raise ValueError("expected check count needs jit/aot modes")
    checks = 0
    for name in cases:
        path = root / name
        if not path.is_file():
            raise ValueError(f"selected case disappeared: {name}")
        rejection = name.startswith("tests/errors/")
        checks += 1 if rejection else len(modes)
        if path.name.startswith("syntax_"):
            if name.startswith("tests/programs/") or rejection and path.read_bytes().startswith(
                    f"# error: {path.name}:".encode()):
                checks += 1
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", "--base-ref", default=os.environ.get("CI_BASE_SHA") or None)
    parser.add_argument("--programs-only", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        evidence = manifest(base=args.base)
        cases = evidence["cases"]
        if args.programs_only:
            cases = [name for name in cases if name.startswith("tests/programs/")]
            evidence = {**evidence, "programs_only": True, "cases": cases,
                        "cases_sha256": hashlib.sha256(("\n".join(cases) + "\n").encode()).hexdigest()}
        if not cases:
            raise ValueError("PR selection is empty")
        text = "\n".join(cases) + "\n"
        if args.output:
            args.output.write_text(text)
        else:
            sys.stdout.write(text)
        if args.manifest:
            args.manifest.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"PR sample: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
