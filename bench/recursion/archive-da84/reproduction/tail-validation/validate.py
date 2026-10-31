#!/usr/bin/env python3
"""Fresh validation after workspace cleanup; never reconstruct old run results.

prepare is read-only with respect to the checkout and invokes no compiler.
fixtures/compare require a released execution lane and fresh bootstrap evidence.
The comparison retains every raw status, diagnostic and complete compressed IR.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
MAIN = "06e3ad5d08514ba31fb231fe4636a962fe6578e3"
MAIN_TREE = "db120afecf27ff03b08c25624dc64be8b06bac3b"
FIXTURE_NAMES = [
    "recursion_guard", "recursion_limit", "recursion_set_limit", "recursion_leaf",
    "recursion_cold", "recursion_bounded", "recursion_partial_depth", "recursion_partial_tails",
    "exc_recursion_unwind", "exc_recursion_contexts", "exc_recursion_cold_uncaught",
    "dynany_recursion_guard", "dynany_recursion_bounded", "gen_recursion_guard",
    "re_specialize", "re_specialize_recursion", "rt_list_vacated",
    "rt_recursion_scoped_files", "lib_weakref_dead", "lib_weakref_callback",
]
LEAF_NAMES = ["recursion_bounded", "recursion_partial_depth", "recursion_partial_tails",
              "dynany_recursion_bounded", "rt_recursion_scoped_files"]
MODES = {
    "normal": ("jit aot", {}, 40),
    "gc-stress": ("jit aot", {"PYSTACHY_GC_STRESS_PROGRAM": "1"}, 40),
    "all-disabled": ("jit aot", {"PYSTACHY_OPT": "-all"}, 40),
    "no-user-inline": ("jit", {"PYSTACHY_JIT_INLINE": "0"}, 20),
    "leaf-disabled": ("jit aot", {"PYSTACHY_OPT": "-recursionleaf"}, 10),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def host_identity():
    models = sorted({line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                     if line.startswith("model name")})
    toolchain = ROOT / "toolchain/manifest.json"
    return {"cpu_models": models, "platform": platform.platform(), "python": sys.version,
            "toolchain_manifest_sha256": digest(toolchain) if toolchain.is_file() else None,
            "historical_amd_timing_series_reused": False}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def require(value, message):
    if not value:
        raise RuntimeError(message)


def git(repo, *arguments):
    return subprocess.check_output(["git", "-C", str(repo), *arguments], text=True).strip()


def corpus(repo):
    result = []
    for pattern in ("pystachy.py", "runtime.py", "tests/programs/*/*.py", "tests/deviations/*.py",
                    "bench/*.py", "bench/pyperformance/*.py", "tests/ir/*.py", "tests/errors/*/*.py"):
        result.extend(str(p.relative_to(repo)) for p in sorted(repo.glob(pattern)) if p.is_file())
    require(len(result) == len(set(result)), "duplicate corpus path")
    return result


def fixture_paths(repo, names):
    result = []
    for name in names:
        paths = list(repo.glob("tests/programs/*/" + name + ".py"))
        require(len(paths) == 1 and paths[0].with_suffix(".out").is_file(), "fixture/expectation missing: " + name)
        result.append(str(paths[0].relative_to(repo)))
    return result


def snapshot(repo, native=True):
    paths = {os.fsdecode(p) for p in subprocess.check_output(
        ["git", "-C", str(repo), "ls-files", "-z"]).split(b"\0") if p}
    for folder in ("src", "lib", "tests", "bench", "mpz", "ryu"):
        for current, dirs, files in os.walk(repo / folder):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".pytest_cache")]
            for name in files:
                path = Path(current) / name
                if path.is_file() and path.suffix not in (".pyc", ".pyo"):
                    paths.add(str(path.relative_to(repo)))
    files = {}
    for name in sorted(paths):
        path = repo / name
        files[name] = {"sha256": digest(path), "bytes": path.stat().st_size} if path.is_file() else {"missing": True}
    data = {"root": str(repo), "commit": git(repo, "rev-parse", "HEAD"),
            "tree": git(repo, "rev-parse", "HEAD^{tree}"),
            "status": git(repo, "status", "--porcelain=v1", "--untracked-files=all"), "files": files}
    if native:
        path = repo / "pystachy"
        data["native_compiler"] = {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}
    return data


def verify_build(repo, evidence_path, expected_commit, expected_tree):
    evidence = json.loads(evidence_path.read_text())
    require(evidence["status"] == "complete" and evidence["exit_code"] == 0
            and evidence["source_identity_stable"] and evidence["before"] == evidence["after"],
            "fresh bootstrap is incomplete or changed sources")
    require(evidence["commit"] == expected_commit and evidence["tree"] == expected_tree,
            "bootstrap source revision mismatch")
    current = snapshot(repo)
    require(current["commit"] == expected_commit and current["tree"] == expected_tree and not current["status"],
            "checkout is not the frozen clean revision")
    for name, fingerprint in evidence["after"].items():
        require(current["files"].get(name, {}).get("sha256") == fingerprint, "bootstrap source mismatch: " + name)
    artifacts = evidence["artifacts"]
    for name in ("pystachy", "build/pystachy1", "build/pystachy2"):
        require(artifacts[name]["sha256"] == current["native_compiler"]["sha256"], "native fixed point differs")
    for prefix in ("stage", "rt"):
        hashes = {artifacts[f"build/{prefix}{number}.ll"]["sha256"] for number in (1, 2, 3)}
        require(len(hashes) == 1, "IR fixed point differs")
    return current, evidence


def environment(cache=None, ircheck=False):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYSTACHY_") and k not in ("PYTHONPATH", "PYTHONHOME", "VALGRIND_LIB")}
    require("PYSTACHY_LLVM" in os.environ, "source the restored pinned toolchain environment first")
    env.update(PYSTACHY_LLVM=os.environ["PYSTACHY_LLVM"], PYSTACHY_JOBS="2", LC_ALL="C")
    if cache is not None:
        env["PYSTACHY_CACHE"] = str(cache)
    if ircheck:
        env["PYSTACHY_IRCHECK"] = "1"
    return env


def replace_once(text, old, new):
    require(text.count(old) == 1, "instrumentation anchor changed: " + repr(old))
    return text.replace(old, new, 1)


def instrument(repo):
    original = (repo / "tools/irsame.sh").read_text()
    text = replace_once(original, 'cd "$(dirname "$0")/.." || exit 1', 'cd "$IRSAME_AUDIT_SOURCE" || exit 1')
    text = replace_once(text,
        'T=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-irsame.XXXXXX") || exit 1\ntrap \'rm -rf "$T"\' EXIT',
        'T=$IRSAME_AUDIT_RESULTS\n[ -d "$T" ] || exit 2\nprintf \'%s\\n\' "$@" > "$T/cases.txt"')
    text = replace_once(text, 'same() {\n', 'same() {\n  printf \'%s\\n\' "$1" > "$2/source.txt"\n  how=$HOW\n  mp=${PYSTACHY_PATH:-}\n')
    text = replace_once(text, '  {\n    [ $a = $b ]',
        '  printf \'%s\\n\' "$a" > "$2/old.status"\n  printf \'%s\\n\' "$b" > "$2/new.status"\n'
        '  printf \'%s\\n\' "$how" > "$2/mode.txt"\n  printf \'%s\\n\' "$mp" > "$2/import-path.txt"\n'
        '  {\n    [ $a = $b ]')
    text = replace_once(text, '  rm -f "$2/old.ll" "$2/new.ll"',
        '  for side in old new; do\n    if [ -f "$2/$side.ll" ]; then\n'
        '      sha256sum "$2/$side.ll" > "$2/$side.ll.sha256" || return\n'
        '      wc -c < "$2/$side.ll" > "$2/$side.ll.bytes" || return\n'
        '      gzip -1 -n "$2/$side.ll" || return\n    fi\n  done\n'
        '  printf \'complete\\n\' > "$2/audit-complete.txt"')
    return original, text


def prepare(args):
    require(git(args.candidate, "rev-parse", "HEAD") == args.expected_candidate_commit
            and git(args.candidate, "rev-parse", "HEAD^{tree}") == args.expected_candidate_tree,
            "candidate source identity changed")
    cases = corpus(args.candidate)
    require(len(cases) == 3918, "unexpected restored corpus denominator")
    original, harness = instrument(args.candidate)
    OUT.mkdir(exist_ok=True)
    (OUT / "irsame-original.sh").write_text(original)
    (OUT / "irsame-prepared.sh").write_text(harness)
    subprocess.run(["/bin/sh", "-n", str(OUT / "irsame-prepared.sh")], check=True)
    (OUT / "prepared-corpus.txt").write_text("\n".join(cases) + "\n")
    plan = {"status": "prepared; no compiler invoked", "prepared_utc": now(),
            "fresh_after_workspace_cleanup": True, "lost_original_local_evidence": "not reconstructed",
            "host": host_identity(),
            "candidate_commit": args.expected_candidate_commit, "candidate_tree": args.expected_candidate_tree,
            "main_commit": MAIN, "main_tree": MAIN_TREE,
            "corpus_cases": len(cases), "corpus_sha256": digest(OUT / "prepared-corpus.txt"),
            "original_harness_sha256": digest(OUT / "irsame-original.sh"),
            "instrumented_harness_sha256": digest(OUT / "irsame-prepared.sh"),
            "controller_sha256": digest(Path(__file__)),
            "fixtures": fixture_paths(args.candidate, FIXTURE_NAMES),
            "leaf_fixtures": fixture_paths(args.candidate, LEAF_NAMES),
            "expected_mode_totals": {k: v[2] for k, v in MODES.items()},
            "contracts_expected": {"typed": 198, "summaries": 7, "compiler_state": 107},
            "execution_gate": "explicit parent lane handoff after bootstrap and performance timings"}
    dump(OUT / "plan.json", plan)
    print(json.dumps(plan, indent=2))


def verify_plan(args):
    plan = json.loads((OUT / "plan.json").read_text())
    require(plan["candidate_commit"] == args.expected_candidate_commit
            and plan["candidate_tree"] == args.expected_candidate_tree,
            "preparation belongs to a different candidate revision")
    require(plan["controller_sha256"] == digest(Path(__file__)), "controller changed since preparation")
    require(plan["corpus_sha256"] == digest(OUT / "prepared-corpus.txt")
            and plan["instrumented_harness_sha256"] == digest(OUT / "irsame-prepared.sh"),
            "prepared corpus or harness changed")


def fixtures(args):
    verify_plan(args)
    before, build = verify_build(args.candidate, args.candidate_build,
                                 args.expected_candidate_commit, args.expected_candidate_tree)
    out = OUT / "fixtures"
    out.mkdir(exist_ok=False)
    dump(out / "sources-before.json", before)
    env = environment(out / "cache", ircheck=True)
    report = {"status": "running", "fresh_after_workspace_cleanup": True, "started_utc": now(),
              "host": host_identity(),
              "candidate_commit": args.expected_candidate_commit, "tree": args.expected_candidate_tree,
              "native_sha256": before["native_compiler"]["sha256"],
              "bootstrap_evidence": str(args.candidate_build), "bootstrap_sha256": digest(args.candidate_build),
              "controller_sha256": digest(Path(__file__)), "python": sys.version,
              "environment": {k: v for k, v in env.items() if k.startswith("PYSTACHY_")}, "results": []}
    dump(out / "evidence.json", report)
    try:
        for name, (modes, extra, expected) in MODES.items():
            names = LEAF_NAMES if name == "leaf-disabled" else FIXTURE_NAMES
            command = ["tests/run.sh", "./pystachy", modes, *fixture_paths(args.candidate, names)]
            log = out / (name + ".log")
            report["active_check"] = name
            dump(out / "evidence.json", report)
            started = time.monotonic()
            with log.open("wb") as stream:
                result = subprocess.run(command, cwd=args.candidate, env=dict(env, **extra),
                                        stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
            text = log.read_text(errors="replace")
            selected = re.findall(r"^selected (\d+) cases$", text, re.MULTILINE)
            totals = re.findall(r"^(\d+) passed, (\d+) failed$", text, re.MULTILINE)
            passed = result.returncode == 0 and selected == [str(len(names))] and totals == [(str(expected), "0")]
            row = {"name": name, "command": command, "environment": extra, "exit_code": result.returncode,
                   "seconds": time.monotonic() - started, "log_sha256": digest(log), "passed": passed,
                   "expected_executions": expected, "selected": selected, "reported_totals": totals}
            report["results"].append(row)
            dump(out / "evidence.json", report)
            print(json.dumps(row), flush=True)
            require(passed, "fixture mode failed: " + name)
        report["status"] = "passed"
    except BaseException as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        after = snapshot(args.candidate)
        dump(out / "sources-after.json", after)
        report.update(finished_utc=now(), source_identity_stable=before == after, active_check=None)
        if before != after:
            report["status"] = "failed"
        dump(out / "evidence.json", report)
    require(report["status"] == "passed", "source identity changed during fixtures")


def compare(args):
    verify_plan(args)
    new, _ = verify_build(args.candidate, args.candidate_build,
                          args.expected_candidate_commit, args.expected_candidate_tree)
    old, _ = verify_build(args.baseline, args.baseline_build, MAIN, MAIN_TREE)
    cases = corpus(args.candidate)
    require(cases == (OUT / "prepared-corpus.txt").read_text().splitlines(), "corpus changed since preparation")
    before = {"old": old, "new": new}
    out = OUT / "irsame"
    out.mkdir(exist_ok=False)
    (out / "cases").mkdir()
    original, harness = instrument(args.candidate)
    require(harness == (OUT / "irsame-prepared.sh").read_text(), "prepared harness changed")
    (out / "irsame-original.sh").write_text(original)
    (out / "irsame-instrumented.sh").write_text(harness)
    dump(out / "sources-before.json", before)
    env = environment()
    env.update(IRSAME_AUDIT_SOURCE=str(args.candidate), IRSAME_AUDIT_RESULTS=str(out / "cases"))
    command = ["/bin/sh", str(out / "irsame-instrumented.sh"), str(args.baseline / "pystachy"), str(args.candidate / "pystachy")]
    report = {"status": "running", "fresh_after_workspace_cleanup": True, "started_utc": now(),
              "host": host_identity(),
              "expected_candidate_commit": args.expected_candidate_commit,
              "expected_candidate_tree": args.expected_candidate_tree,
              "command": command, "cwd": str(args.candidate), "jobs": 2, "expected_cases": len(cases),
              "compiler_home_unset": "PYSTACHY_HOME" not in env, "controller_sha256": digest(Path(__file__)),
              "effective_pystachy_environment": {k: v for k, v in env.items() if k.startswith("PYSTACHY_")},
              "candidate_build": str(args.candidate_build), "candidate_build_sha256": digest(args.candidate_build),
              "baseline_build": str(args.baseline_build), "baseline_build_sha256": digest(args.baseline_build)}
    dump(out / "run.json", report)
    started = time.monotonic()
    try:
        with (out / "harness.log").open("wb") as log:
            result = subprocess.run(command, cwd=args.candidate, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=3600)
        report["harness_exit_status"] = result.returncode
        report["status"] = "captured"
    except BaseException as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        after = {"old": snapshot(args.baseline), "new": snapshot(args.candidate)}
        dump(out / "sources-after.json", after)
        report.update(finished_utc=now(), seconds=time.monotonic() - started, source_identity_stable=before == after)
        dump(out / "run.json", report)
    require((out / "cases/cases.txt").read_text().splitlines() == cases, "captured corpus differs")
    audit(args)


def audit(args):
    out = OUT / "irsame"
    before = json.loads((out / "sources-before.json").read_text())
    after = json.loads((out / "sources-after.json").read_text())
    run = json.loads((out / "run.json").read_text())
    for identity in (before["new"], after["new"]):
        require(identity["commit"] == args.expected_candidate_commit
                and identity["tree"] == args.expected_candidate_tree,
                "captured candidate revision differs from the requested audit")
    require(run["expected_candidate_commit"] == args.expected_candidate_commit
            and run["expected_candidate_tree"] == args.expected_candidate_tree,
            "capture command expected a different candidate revision")
    cases = (out / "cases/cases.txt").read_text().splitlines()
    require(len(cases) == 3918 and len(set(cases)) == len(cases), "comparison corpus incomplete")
    common = {}
    for name, data in before["old"]["files"].items():
        if name.startswith("lib/") and name.endswith(".py") and "sha256" in data and data == before["new"]["files"].get(name):
            common[str(Path(before["old"]["root"]) / name).encode()] = name
    pattern = re.compile(b"|".join(re.escape(name) for name in sorted(common, key=len, reverse=True)))
    mapping, rows, issues = {}, [], []
    counts = Counter(total=len(cases))
    for index, filename in enumerate(cases, 1):
        folder = out / "cases" / str(index)
        require((folder / "source.txt").read_bytes() == (filename + "\n").encode(), "case source record differs from corpus")
        expected_mode = "rt" if filename == "runtime.py" or filename.endswith("/runtime.py") or Path(filename).name.startswith("rtmode_") else "ir"
        require((folder / "mode.txt").read_bytes() == (expected_mode + "\n").encode(), "case compiler mode mismatch")
        row = {"index": index, "file": filename, "artifacts": "cases/" + str(index),
               "mode": expected_mode, "complete": (folder / "audit-complete.txt").exists(), "replacements": []}
        raw = {}
        for side in ("old", "new"):
            raw[side] = (folder / (side + ".msg")).read_bytes()
            status = int((folder / (side + ".status")).read_text())
            require(status in (0, 1), "unexpected compiler exit status")
            ir = folder / (side + ".ll.gz")
            sidecars = [folder / (side + ".ll.sha256"), folder / (side + ".ll.bytes")]
            presence = [ir.exists(), *[path.exists() for path in sidecars]]
            require(all(presence) or not any(presence), "retained IR archive/sidecar presence mismatch")
            require(status != 0 or all(presence), "successful compilation lacks retained IR")
            value = {"status": status, "messages_sha256": hashlib.sha256(raw[side]).hexdigest(), "ir_sha256": None}
            if ir.exists():
                expected = (folder / (side + ".ll.sha256")).read_text().split()[0]
                size = int((folder / (side + ".ll.bytes")).read_text())
                h, actual_size = hashlib.sha256(), 0
                with gzip.open(ir, "rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        h.update(block)
                        actual_size += len(block)
                require(h.hexdigest() == expected and actual_size == size, "retained IR archive mismatch")
                value.update(ir_sha256=expected, ir_bytes=size, compressed_sha256=digest(ir))
            row[side] = value
            counts[side + "_exit_" + str(status)] += 1
        reconstructed, end = [], 0
        if raw["old"] != raw["new"]:
            counts["messages_changed"] += 1
            for match in pattern.finditer(raw["old"]):
                location = re.match(rb":\d+(?::\d+)?", raw["old"][match.end():])
                prefix = raw["old"][:match.start()]
                context = "header" if match.start() == 0 or prefix.endswith(b"\n") else "nested_call_location" if prefix.endswith(b"for the call at ") else ""
                if not location or not context:
                    continue
                name = common[match.group()]
                old_path, new_path = Path(before["old"]["root"]) / name, Path(before["new"]["root"]) / name
                if name not in mapping:
                    require(old_path.read_bytes() == new_path.read_bytes()
                            and digest(old_path) == before["old"]["files"][name]["sha256"], "library filename substitution is not content-identical")
                    mapping[name] = {"old_filename": str(old_path), "new_filename": str(new_path), "source_sha256": digest(old_path)}
                reconstructed.extend([raw["old"][end:match.start()], str(new_path).encode()])
                end = match.end()
                row["replacements"].append({"filename": name, "old_byte_offset": match.start(), "context": context,
                                             "unchanged_source_location": location.group().decode()})
                counts[context + "_replacements"] += 1
        reconstructed.append(raw["old"][end:])
        same_message = b"".join(reconstructed) == raw["new"]
        row["diagnostic_filename_only"] = same_message
        row["messages_changed"] = raw["old"] != raw["new"]
        row["status_changed"] = row["old"]["status"] != row["new"]["status"]
        row["new_rejection"] = row["old"]["status"] == 0 and row["new"]["status"] != 0
        row["new_acceptance"] = row["old"]["status"] != 0 and row["new"]["status"] == 0
        a, b = row["old"]["ir_sha256"], row["new"]["ir_sha256"]
        row["ir_classification"] = "both_absent" if a is None and b is None else "old_only" if b is None else "new_only" if a is None else "identical" if a == b else "different"
        counts["ir_" + row["ir_classification"]] += 1
        for key in ("status_changed", "new_rejection", "new_acceptance"):
            counts[key] += row[key]
        if not row["complete"] or row["status_changed"] or not same_message or row["ir_classification"] in ("old_only", "new_only"):
            issues.append(index)
        rows.append(row)
    stable = before == after and run["source_identity_stable"]
    runtime_same = next(row["ir_classification"] == "identical" for row in rows if row["file"] == "runtime.py")
    result = {"status": "passed" if stable and not issues and runtime_same and run["harness_exit_status"] in (0, 1) else "review_required",
              "fresh_after_workspace_cleanup": True, "scope": "new compilation/status/diagnostic parity only; intentional IR changes are retained, not runtime equivalence",
              "counts": dict(counts), "source_identity_stable": stable,
              "harness_exit_status_preserved": run["harness_exit_status"], "remaining_review_cases": issues,
              "filename_mapping": mapping, "runtime_ir_identical": runtime_same,
              "all_retained_ir_archives_rehashed": True, "results": rows}
    dump(out / "irsame-audit.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("results", "filename_mapping")}, indent=2))
    require(result["status"] == "passed", "comparison requires review")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "fixtures", "compare", "audit"))
    parser.add_argument("--candidate", type=Path, default=ROOT / "pystachy")
    parser.add_argument("--baseline", type=Path, default=ROOT / "baselines/main")
    parser.add_argument("--candidate-build", type=Path, default=ROOT / "recovery-validation/candidate/bootstrap.json")
    parser.add_argument("--baseline-build", type=Path, default=ROOT / "recovery-validation/main/bootstrap.json")
    parser.add_argument("--expected-candidate-commit", required=True, help="Independently pinned full candidate commit SHA")
    parser.add_argument("--expected-candidate-tree", required=True, help="Independently pinned full candidate tree SHA")
    args = parser.parse_args()
    for identity in (args.expected_candidate_commit, args.expected_candidate_tree):
        if re.fullmatch("[0-9a-f]{40}", identity) is None:
            parser.error("expected candidate commit and tree must be full lowercase 40-character SHA values")
    for key in ("candidate", "baseline", "candidate_build", "baseline_build"):
        setattr(args, key, getattr(args, key).resolve())
    {"prepare": prepare, "fixtures": fixtures, "compare": compare, "audit": audit}[args.action](args)


if __name__ == "__main__":
    main()
