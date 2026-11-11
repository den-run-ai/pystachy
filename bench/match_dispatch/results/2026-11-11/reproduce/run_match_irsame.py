#!/usr/bin/env python3
"""Compare the pinned match candidate against its reference, preserving evidence.

The reference must already have been built with make ref REF=<base>. No builds
are performed here. --prepare-only writes source/input and syntax evidence
without requiring a reference executable or running the corpus comparison.

Exit status: 0 prepared/identical; 1 completed with differences; 2 incomplete or
failed preflight. Expected-difference candidates are leads, never an allowlist.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys


BASE = "b40ee875bf72b86804c4f5a300066f4f7c3eb20b"
CANDIDATE = "620c35f42d8c35d7a27341bbe4ba259b043b959d"
SHARED_INPUTS = (
    "pystachy.py", "runtime.c", "runtime.py", "VERSION", "lljit.c",
    "pyembed.c", "pyext.c", "ryu", "mpz", "lib",
)
REFERENCE_INPUTS = (
    "pystachy.py", "src", "runtime.c", "runtime.py", "lib", "ryu", "mpz",
)
CORPUS_GLOBS = (
    "pystachy.py", "runtime.py", "tests/programs/*/*.py",
    "tests/deviations/*.py", "bench/*.py", "bench/pyperformance/*.py",
    "tests/ir/*.py", "tests/errors/*/*.py",
)
EXTRA_INPUTS = (
    "bench/match_dispatch/workload.py",
    "examples/match_dispatch/dispatch.py",
)
SYNTAX_FIXTURE = "tests/errors/syntax/syntax_match_duplicate_key_over_limit.py"
SYNTAX_INTRO = "290afebe2"
SYNTAX_INTRO_PATH = "tests/errors/syntax_match_duplicate_key_over_limit.py"


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def git_text(repo, *args):
    return git(repo, *args).decode().strip()


def tree(repo, ref, paths):
    entries = {}
    for row in git(repo, "ls-tree", "-r", "-z", ref, "--", *paths).split(b"\0"):
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        path = raw_path.decode()
        if path.endswith(".md"):
            continue
        if kind != "blob" or mode not in ("100644", "100755"):
            raise RuntimeError(f"unsupported source entry: {mode} {kind} {path}")
        entries[path] = {"mode": mode, "blob_id": blob}
    return entries


def file_identity(path):
    raw = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    mode = "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"
    return {"mode": mode, "git_blob_id": blob,
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def verify_files(directory, entries):
    result = []
    for path, entry in sorted(entries.items()):
        local = directory / path
        if local.is_symlink() or not local.is_file():
            raise RuntimeError(f"missing/non-regular source file: {local}")
        actual = file_identity(local)
        if actual["git_blob_id"] != entry["blob_id"] or actual["mode"] != entry["mode"]:
            raise RuntimeError(f"source bytes/mode differ from commit: {local}")
        result.append({"path": path, **entry, "worktree": actual})
    return result


def unexpected_sources(repo):
    tracked = set(git(repo, "ls-files", "-z").decode().split("\0"))
    extra = []
    for directory in ("src", "lib", "tests", "bench", "examples", "ports", "tools", "mpz", "ryu"):
        for path in (repo / directory).rglob("*"):
            if path.is_file() and path.suffix in (".py", ".c", ".h"):
                name = path.relative_to(repo).as_posix()
                if name not in tracked:
                    extra.append(name)
    return sorted(extra)


def parser_method(source, name):
    module = ast.parse(source)
    parser = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Parser")
    method = next(node for node in parser.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, method)


def syntax_evidence(repo, base, candidate, native, env):
    raw = (repo / SYNTAX_FIXTURE).read_bytes()
    intro = git_text(repo, "rev-parse", f"{SYNTAX_INTRO}^{{commit}}")
    old = git(repo, "show", f"{base}:{SYNTAX_FIXTURE}")
    introduced = git(repo, "show", f"{intro}:{SYNTAX_INTRO_PATH}")
    parser_path = "src/pystachy_compiler/parser.py"
    old_parser = git(repo, "show", f"{base}:{parser_path}").decode()
    new_parser = git(repo, "show", f"{candidate}:{parser_path}").decode()
    lexer_path = "src/pystachy_compiler/lexer.py"
    result = {
        "fixture": SYNTAX_FIXTURE, "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "fixture_unchanged_from_base": raw == old,
        "fixture_identical_to_introduced_source": raw == introduced,
        "introduced_commit": intro, "introduced_path": SYNTAX_INTRO_PATH,
        "introduced_commit_metadata": git_text(repo, "show", "-s", "--format=%H%n%aI%n%s", intro),
        "introduced_commit_url": f"https://github.com/den-run-ai/pystachy/commit/{intro}",
        "base_fixture_url": f"https://github.com/den-run-ai/pystachy/blob/{base}/{SYNTAX_FIXTURE}",
        "parser_pcheck_unchanged": parser_method(old_parser, "pcheck") == parser_method(new_parser, "pcheck"),
        "lexer_unchanged": git(repo, "show", f"{base}:{lexer_path}") == git(repo, "show", f"{candidate}:{lexer_path}"),
        "python": sys.version, "python_executable": sys.executable,
        "int_max_str_digits": sys.get_int_max_str_digits(),
        "finding": "Pre-existing intentional rejection-diagnostic difference: CPython cannot format the duplicate integer key past its decimal string limit and raises ValueError; Pystachy reports the duplicate in hexadecimal. The fixture has documented this since its introduction. No accepted-program behavior difference.",
    }
    try:
        compile(raw, SYNTAX_FIXTURE, "exec")
        result["cpython"] = {"status": "accepted"}
    except (SyntaxError, ValueError) as error:
        result["cpython"] = {"status": "rejected", "exception": type(error).__name__,
                             "message": str(error), "line": getattr(error, "lineno", None)}
    checked = subprocess.run([str(native), "check", SYNTAX_FIXTURE], cwd=repo, env=env,
                             capture_output=True, text=True, timeout=30, check=False)
    result["native_candidate"] = {"exit_status": checked.returncode, "stdout": checked.stdout,
                                  "stderr": checked.stderr}
    if not all(result[key] for key in ("fixture_unchanged_from_base", "fixture_identical_to_introduced_source",
                                      "parser_pcheck_unchanged", "lexer_unchanged")):
        raise RuntimeError("syntax baseline provenance no longer matches the recorded finding")
    return result


def inventory(repo, candidate):
    files = [path.relative_to(repo).as_posix() for pattern in CORPUS_GLOBS
             for path in sorted(repo.glob(pattern)) if path.is_file()]
    tracked = git(repo, "ls-tree", "-r", "--name-only", "-z", candidate).decode().split("\0")
    expected = []
    for pattern in CORPUS_GLOBS:
        pattern_parts = pattern.split("/")
        expected.extend(sorted(path for path in tracked if path
                               and len(path.split("/")) == len(pattern_parts)
                               and all(fnmatch.fnmatchcase(part, glob) for part, glob
                                       in zip(path.split("/"), pattern_parts, strict=True))))
    if files != expected or len(set(files)) != len(files):
        raise RuntimeError("worktree corpus inventory differs from the candidate commit")
    if candidate == CANDIDATE and len(files) != 4435:
        raise RuntimeError(f"original candidate inventory differs from reviewed 4435 inputs: {len(files)}")
    for path in EXTRA_INPUTS:
        if not (repo / path).is_file() or path in files:
            raise RuntimeError(f"missing/duplicate extra consumer: {path}")
        files.append(path)
    return files


def expected_candidates(repo, base, candidate):
    added = git_text(repo, "diff", "--name-only", "--diff-filter=A", base, candidate).splitlines()
    programs = [path for path in added if path.startswith("tests/programs/") and path.endswith(".py")]
    rejections = [path for path in added if path.startswith("tests/errors/") and path.endswith(".py")]
    if candidate == CANDIDATE and (len(programs) != 13 or len(rejections) != 15):
        raise RuntimeError("feature/regression inventory differs from reviewed 13 programs / 15 rejections")
    result = {path: "new bounded-match executable regression: base rejection to IR expected" for path in programs}
    result.update({path: "new bounded rejection diagnostic; earlier existing rejection may remain identical" for path in rejections})
    result.update({path: "new bounded-match consumer: base rejection to IR expected" for path in EXTRA_INPUTS})
    result["tests/errors/library/lib_statistics_kde.py"] = "match lowers; next existing function-storage rejection becomes visible"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--candidate", default=CANDIDATE,
                        help="reviewed candidate commit SHA; HEAD and worktree must match it")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "match_irsame_evidence")
    parser.add_argument("--llvm", default=os.environ.get("PYSTACHY_LLVM", ""))
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    repo, output = args.repo.resolve(), args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "match-irsame-report.json"
    if report_path.exists():
        previous = json.loads(report_path.read_text())
        if previous.get("status") != "prepared":
            parser.error("output contains a previous run; choose a new --output-dir to preserve it")
    report = {"schema_version": 1, "status": "preflight", "started_utc": timestamp(),
              "repository": str(repo), "base_commit": BASE, "candidate_commit": args.candidate,
              "controller": file_identity(Path(__file__).resolve()),
              "artifact_directory": str(output), "comparison_executed": False}
    write_json(report_path, report)
    try:
        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", args.candidate):
            raise RuntimeError("--candidate must be an explicit commit SHA")
        candidate = git_text(repo, "rev-parse", f"{args.candidate}^{{commit}}")
        report["candidate_commit"] = candidate
        if git_text(repo, "rev-parse", "HEAD") != candidate:
            raise RuntimeError("HEAD is not the reviewed candidate commit")
        if git_text(repo, "rev-parse", f"{BASE}^{{commit}}") != BASE:
            raise RuntimeError("reference commit cannot be resolved exactly")
        if git(repo, "diff", "--name-only", candidate, "--"):
            raise RuntimeError("tracked worktree/index differs from the reviewed candidate")
        extra = unexpected_sources(repo)
        if extra:
            raise RuntimeError(f"untracked/ignored source inputs: {extra}")
        for ref, key in ((BASE, "base_tree"), (candidate, "candidate_tree")):
            report[key] = git_text(repo, "rev-parse", f"{ref}^{{tree}}")
        old_inputs, new_inputs = tree(repo, BASE, SHARED_INPUTS), tree(repo, candidate, SHARED_INPUTS)
        if old_inputs != new_inputs or len(old_inputs) != 105:
            raise RuntimeError("runtime/library inputs differ or reviewed 105-file inventory changed")
        verified = verify_files(repo, old_inputs)
        for row in verified:
            row["base_blob_id"] = old_inputs[row["path"]]["blob_id"]
            row["candidate_blob_id"] = new_inputs[row["path"]]["blob_id"]
        proof = {"schema_version": 1, "verified_utc": timestamp(), "base_commit": BASE,
                 "candidate_commit": candidate, "file_count": len(verified),
                 "library_python_files": sum(row["path"].startswith("lib/") and row["path"].endswith(".py") for row in verified),
                 "selection": list(SHARED_INPUTS), "excluded_suffixes": [".md"],
                 "untracked_or_ignored_source_inputs": extra, "files": verified,
                 "conclusion": "These executable inputs have identical blob IDs, modes and actual worktree bytes. A common PYSTACHY_HOME is justified for comparison without rewriting IR or substituting different library/runtime code."}
        write_json(output / "match-identical-inputs.json", proof)
        report["shared_input_proof"] = "match-identical-inputs.json"
        files = inventory(repo, candidate)
        inventory_path = output / "match-irsame-inputs.txt"
        inventory_path.write_text("\n".join(files) + "\n")
        report["inventory"] = {"path": inventory_path.name, "count": len(files),
                               "default_count": len(files) - len(EXTRA_INPUTS), "extra_consumers": list(EXTRA_INPUTS),
                               "sha256": file_identity(inventory_path)["sha256"]}
        candidates = expected_candidates(repo, BASE, candidate)
        report["expected_difference_candidates"] = candidates
        report["difference_policy"] = "Candidate list is not an allowlist. Every difference requires review. Any previously accepted program newly rejected is a blocker. No IR bytes are normalized."
        env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env.update(LC_ALL="C", PYTHONDONTWRITEBYTECODE="1", PYSTACHY_HOME=str(repo),
                   PYSTACHY_JOBS="2", PYSTACHY_PROGRAM_CACHE="0")
        if args.llvm:
            env["PYSTACHY_LLVM"] = args.llvm
        native = repo / "pystachy"
        if not native.is_file() or not os.access(native, os.X_OK):
            raise RuntimeError("candidate native compiler is missing/not executable")
        report["candidate_executable"] = {"path": str(native), **file_identity(native)}
        report["binary_provenance_limit"] = "Executable hashes and source snapshots are recorded; native binary-to-source provenance also relies on the accompanying successful build/fixed-point logs."
        write_json(output / "match-syntax-baseline.json", syntax_evidence(repo, BASE, candidate, native, env))
        report["syntax_baseline"] = "match-syntax-baseline.json"
        if args.prepare_only:
            report.update(status="prepared", finished_utc=timestamp())
            write_json(report_path, report)
            print(json.dumps({"status": "prepared", "inputs": len(files), "identical_input_files": len(verified),
                              "report": str(report_path)}))
            return 0
        reference = repo / "build/ref"
        if (reference / "commit").read_text().strip() != BASE:
            raise RuntimeError("build/ref/commit does not identify the reference commit")
        reference_sources = tree(repo, BASE, REFERENCE_INPUTS)
        ref_verified = verify_files(reference, reference_sources)
        for directory in ("src", "lib", "mpz", "ryu"):
            for path in (reference / directory).rglob("*"):
                if path.is_file() and path.suffix in (".py", ".c", ".h"):
                    if path.relative_to(reference).as_posix() not in reference_sources:
                        raise RuntimeError(f"unexpected reference source: {path}")
        old = reference / "pystachy"
        if not old.is_file() or not os.access(old, os.X_OK):
            raise RuntimeError("reference native compiler is missing/not executable")
        report["reference_source_snapshot"] = {"file_count": len(ref_verified), "files": ref_verified}
        report["reference_executable"] = {"path": str(old), **file_identity(old)}
        times = output / "match-irsame-case-times.log"
        times.write_text("")
        env["PYSTACHY_CASE_TIMES"] = str(times)
        report["environment"] = {key: value for key, value in env.items()
                                 if key.startswith("PYSTACHY_") or key in ("LC_ALL", "PYTHONDONTWRITEBYTECODE")}
        script_path = repo / "tools/irsame.sh"
        script = script_path.read_text()
        if script.count("\nSHOW=3\n") != 1:
            raise RuntimeError("irsame SHOW cap differs from the reviewed script")
        expanded = script.replace("\nSHOW=3\n", f"\nSHOW={len(files)}\n")
        report["irsame_script"] = {"path": "tools/irsame.sh", **file_identity(script_path),
                                   "only_change": f"SHOW=3 -> SHOW={len(files)} (in memory only)",
                                   "executed_text_sha256": hashlib.sha256(expanded.encode()).hexdigest()}
        log_path = output / "match-irsame-full.log"
        command = ["/bin/sh", "-c", expanded, "tools/irsame.sh", "build/ref/pystachy", "./pystachy", *files]
        report.update(status="running", comparison_executed=True, comparison_started_utc=timestamp(),
                      log=log_path.name, case_times=times.name)
        write_json(report_path, report)
        with log_path.open("w") as log:
            process = subprocess.Popen(command, cwd=repo, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                returncode = process.wait()
            except BaseException:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
        text = log_path.read_text()
        differences = re.findall(r"^DIFF (.+)$", text, re.MULTILINE)
        same = re.findall(r"^(\d+) programs identical$", text, re.MULTILINE)
        different = re.findall(r"^(\d+) of (\d+) differ$", text, re.MULTILINE)
        if len(same) + len(different) != 1:
            raise RuntimeError("missing/ambiguous final comparison count")
        total = int(same[0]) if same else int(different[0][1])
        count = 0 if same else int(different[0][0])
        timing_rows = [line.split(" ", 1) for line in times.read_text().splitlines()]
        timing_counts = Counter(row[1] for row in timing_rows if len(row) == 2 and row[0].isdigit())
        infrastructure_errors = [line for line in text.splitlines() if line.strip() in
                                 ("no result (its worker died)", "cannot prepare import path", "cannot normalize diagnostics")]
        complete = (returncode in (0, 1) and total == len(files) and count == len(differences)
                    and len(differences) == len(set(differences)) and set(differences) <= set(files)
                    and timing_counts == Counter(files) and len(timing_rows) == len(files)
                    and not infrastructure_errors and (returncode == 0) == (count == 0))
        unexpected = sorted(set(differences) - set(candidates))
        status = ("incomplete" if not complete else "unexpected_differences" if unexpected
                  else "completed_with_differences" if count else "identical")
        report.update(status=status, finished_utc=timestamp(), comparison_exit_status=returncode,
                      comparison_complete=complete, total_inputs=total, differing_count=count,
                      identical_count=total-count, differing_cases=differences,
                      unexpected_differing_cases=unexpected, completed_timing_rows=len(timing_rows),
                      infrastructure_errors=infrastructure_errors,
                      manual_difference_review_required=bool(differences))
        write_json(report_path, report)
        print(json.dumps({"status": status, "total": total, "identical": total-count,
                          "differing": count, "unexpected": unexpected, "report": str(report_path)}))
        return returncode if complete else 2
    except BaseException as error:
        report.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else
                      "incomplete" if report["comparison_executed"] else "preflight_failed",
                      finished_utc=timestamp(), error=f"{type(error).__name__}: {error}")
        write_json(report_path, report)
        print(json.dumps({"status": report["status"], "error": report["error"], "report": str(report_path)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
