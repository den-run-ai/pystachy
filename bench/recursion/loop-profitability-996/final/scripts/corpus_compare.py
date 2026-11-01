#!/usr/bin/env python3
"""Record one run of unmodified tools/irsame.sh, then assess diagnostic paths.

The shell oracle keeps its own byte-exact verdict and exit status. Recording
adapters execute each native compiler with the oracle's exact arguments and
environment, forward its complete combined output, and preserve per-case data
before the oracle removes its temporary files. This does not execute programs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import time


PATTERNS = (
    "pystachy.py", "runtime.py", "tests/programs/*/*.py", "tests/deviations/*.py",
    "bench/*.py", "bench/pyperformance/*.py", "tests/ir/*.py", "tests/errors/*/*.py",
)
RECURSION_CASES = (
    "bench/recursion/json_calls.py", "bench/recursion/json_file_calls.py",
    "bench/recursion/object_calls.py", "bench/recursion/ordinary_calls.py",
)
PINNED_BASE = "ea68529b8a590eb8f3df7200b857e1d16becd7a3"


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_record(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    info = path.stat()
    return {"sha256": digest.hexdigest(), "bytes": info.st_size,
            "mode": stat.S_IMODE(path.lstat().st_mode),
            "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns,
            "symlink": os.readlink(path) if path.is_symlink() else None}


def json_write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def command(command, cwd=None, env=None, check=True):
    result = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {command!r}: "
                           + result.stderr.decode("utf-8", "backslashreplace"))
    return result


def candidate_manifest(root):
    names = command(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                    cwd=root).stdout.split(b"\0")
    files = {}
    for name in sorted(set(os.fsdecode(item) for item in names if item)):
        path = root / name
        files[name] = file_record(path) if path.is_file() else {"missing_or_not_regular": True}
    return {"head": command(["git", "rev-parse", "HEAD"], cwd=root).stdout.decode().strip(),
            "status": command(["git", "status", "--porcelain=v1", "--untracked-files=all"],
                              cwd=root).stdout.decode("utf-8", "backslashreplace"),
            "files": files}


def reference_manifest(home):
    names = {"pystachy.py", "runtime.py", "runtime.c", "commit"}
    for directory in ("src", "lib", "ryu", "mpz"):
        names.update(str(path.relative_to(home)) for path in (home / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    return {name: file_record(home / name) for name in sorted(names) if (home / name).is_file()}


def native_snapshot(config):
    root = Path(config["root"])
    return {
        "candidate": candidate_manifest(root),
        "reference": reference_manifest(Path(config["old"]).parent),
        "executables": {role: file_record(config[role]) for role in ("old", "new")},
        "controller": file_record(config["controller"]),
        "oracle": file_record(root / "tools/irsame.sh"),
        "path_helper": file_record(root / "tests/prepare_path.sh"),
    }


def oracle_cases(root, env):
    source = (root / "tools/irsame.sh").read_text()
    match = re.search(r"if \[ \$# = 0 \]; then\s+for f in (.*?); do", source, re.S)
    if not match:
        raise RuntimeError("cannot verify the oracle's corpus enumeration")
    actual = tuple(match.group(1).replace("\\\n", " ").split())
    if actual != PATTERNS:
        raise RuntimeError(f"oracle corpus changed; review controller before running: {actual!r}")
    script = "for f in " + " ".join(PATTERNS) + "; do [ ! -f \"$f\" ] || printf '%s\\0' \"$f\"; done"
    raw = command(["sh", "-c", script], cwd=root, env=env).stdout
    cases = [os.fsdecode(path) for path in raw.split(b"\0") if path]
    if len(cases) != len(set(cases)) or not cases:
        raise RuntimeError("empty or duplicate corpus enumeration")
    return cases


def execute_native(argv, timeout):
    started = time.monotonic()
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    timed_out = False
    try:
        output = process.communicate(timeout=timeout)[0]
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        output = process.communicate()[0]
    status = 124 if timed_out else (128 - process.returncode if process.returncode < 0 else process.returncode)
    return output, {"returncode": process.returncode, "shell_status": status,
                    "timed_out": timed_out, "elapsed_s": time.monotonic() - started}


def capture_prepared_paths(config, directory, temporary):
    root = Path(config["root"])
    records = []
    for raw in os.environ.get("PYSTACHY_PATH", "").split(":"):
        if not raw:
            continue
        path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        entry = {"spelling": raw, "absolute": str(path), "exists": path.exists()}
        if path.exists() and not path.is_relative_to(root):
            if not path.is_relative_to(temporary):
                raise RuntimeError(f"unexpected external fixture directory: {path}")
            entry["files"] = {}
            for item in sorted(path.rglob("*")):
                if not item.is_file():
                    continue
                relative = item.relative_to(path)
                saved = directory / "prepared-path" / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                data = item.read_bytes()
                if saved.exists() and saved.read_bytes() != data:
                    raise RuntimeError("prepared fixture changed between compilers")
                saved.write_bytes(data)
                entry["files"][str(relative)] = file_record(item)
        records.append(entry)
    return records


def compare_row(directory, case, index):
    old = json.loads((directory / "old.json").read_text())
    new = json.loads((directory / "new.json").read_text())
    old_message = (directory / "old.msg").read_bytes()
    new_message = (directory / "new.msg").read_bytes()
    old_ir, new_ir = directory / "old.ll", directory / "new.ll"
    ir_present = [old_ir.exists(), new_ir.exists()]
    ir_equal = ir_present[0] == ir_present[1]
    changes = {"old_lines": 0, "new_lines": 0}
    if all(ir_present):
        ir_equal = old["ir"] == new["ir"]
        if not ir_equal:
            difference = command(["diff", "--old-line-format=O", "--new-line-format=N",
                                  "--unchanged-line-format=", str(old_ir), str(new_ir)], check=False)
            if difference.returncode not in (0, 1):
                raise RuntimeError("IR diff failed: " + difference.stderr.decode(errors="replace"))
            changes = {"old_lines": difference.stdout.count(b"O"),
                       "new_lines": difference.stdout.count(b"N")}
    messages_equal = old_message == new_message
    if not messages_equal:
        difference = command(["diff", "-u", "--label", "old.msg", "--label", "new.msg",
                              str(directory / "old.msg"), str(directory / "new.msg")], check=False)
        if difference.returncode not in (0, 1):
            raise RuntimeError("diagnostic diff failed")
        (directory / "diagnostics.diff").write_bytes(difference.stdout)
    row = {"index": index, "case": case, "old": old, "new": new,
           "status_equal": old["shell_status"] == new["shell_status"],
           "messages_equal": messages_equal, "ir_present": ir_present,
           "ir_equal": ir_equal, "ir_line_changes": changes,
           "validation_errors": []}
    if old["mode"] != new["mode"]:
        row["validation_errors"].append("compiler modes differ")
    if old["timed_out"] or new["timed_out"]:
        row["validation_errors"].append("native compiler timeout")
    if old["shell_status"] not in (0, 1) or new["shell_status"] not in (0, 1):
        row["validation_errors"].append("abnormal native compiler exit status")
    if old["prepared_paths"] != new["prepared_paths"]:
        row["validation_errors"].append("prepared import paths differ")
    row["strict_equal"] = row["status_equal"] and messages_equal and ir_equal
    for path in (old_ir, new_ir):
        if not path.exists():
            continue
        if not ir_equal:
            with path.open("rb") as source, gzip.GzipFile(str(path) + ".gz", "wb", mtime=0) as target:
                shutil.copyfileobj(source, target)
        path.unlink()
    json_write(directory / "comparison.json", row)


def worker(config_path, role, arguments):
    config = json.loads(Path(config_path).read_text())
    output_root = Path(config["output"])
    if not arguments:
        output, result = execute_native([config[role]], 60)
        (output_root / ("usage-" + role + ".msg")).write_bytes(output)
        json_write(output_root / ("usage-" + role + ".json"), result)
        sys.stdout.buffer.write(output)
        return result["shell_status"]
    if len(arguments) != 4 or arguments[0] not in ("ir", "rt") or arguments[2] != "-o":
        raise RuntimeError(f"unexpected oracle compiler invocation: {arguments!r}")
    case = arguments[1]
    index = config["cases"].index(case) + 1
    directory = output_root / "cases" / f"{index:05d}"
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / (role + ".json")).exists():
        raise RuntimeError("duplicate compiler observation")
    prepared = capture_prepared_paths(config, directory, Path(arguments[3]).parent.resolve())
    output, result = execute_native([config[role], *arguments], config["timeout_s"])
    (directory / (role + ".msg")).write_bytes(output)
    result.update(mode=arguments[0], argv=[config[role], *arguments],
                  source_sha256=file_record(Path(config["root"]) / case)["sha256"],
                  message_sha256=sha_bytes(output), message_bytes=len(output),
                  prepared_paths=prepared, ir=None)
    generated = Path(arguments[3])
    if generated.exists():
        shutil.copyfile(generated, directory / (role + ".ll"))
        record = file_record(generated)
        result["ir"] = {key: record[key] for key in ("sha256", "bytes")}
    json_write(directory / (role + ".json"), result)
    if role == "new":
        try:
            compare_row(directory, case, index)
        except Exception as error:
            json_write(directory / "recording-error.json", {"error": repr(error)})
    # Only the native compiler's bytes and native shell status reach irsame.sh.
    sys.stdout.buffer.write(output)
    return result["shell_status"]


class DiagnosticProof:
    def __init__(self, config, before, after):
        self.config = config
        self.before = before
        self.after = after
        self.root = Path(config["root"])
        self.old_lib = Path(config["old"]).parent / "lib"
        self.new_lib = self.root / "lib"
        self.prefixes = [os.fsencode(str(path)) + b"/" for path in (self.old_lib, self.new_lib)]
        self.files = {}
        # Match only a complete absolute Python source filename under an exact
        # known library home, not arbitrary checkout-prefix substrings.
        self.pattern = re.compile(rb"(?<![A-Za-z0-9_./-])(?:" + b"|".join(
            re.escape(prefix) for prefix in sorted(self.prefixes, key=len, reverse=True))
            + rb")[A-Za-z0-9_./-]+\.py(?=$|[:\s'\"()\[\],;>])")

    def verify_file(self, relative):
        if relative in self.files:
            return self.files[relative]
        if ".." in Path(relative).parts:
            raise ValueError("parent traversal in diagnostic path")
        key = "lib/" + relative
        old_before = self.before["reference"].get(key)
        old_after = self.after["reference"].get(key)
        new_before = self.before["candidate"]["files"].get(key)
        new_after = self.after["candidate"]["files"].get(key)
        records = [old_before, old_after, new_before, new_after]
        if any(record is None or record.get("symlink") is not None or "sha256" not in record for record in records):
            raise ValueError("path is not a snapshotted regular library source")
        if old_before != old_after or new_before != new_after or old_before["sha256"] != new_before["sha256"]:
            raise ValueError("library source bytes changed or differ")
        blob = command(["git", "show", self.config["base_ref"] + ":" + key], cwd=self.root).stdout
        if sha_bytes(blob) != old_before["sha256"]:
            raise ValueError("library source differs from the pinned baseline Git blob")
        proof = {"relative": key, "old_path": str(self.old_lib / relative),
                 "new_path": str(self.new_lib / relative), "sha256": sha_bytes(blob),
                 "bytes": len(blob), "baseline_git_ref": self.config["base_ref"],
                 "before_and_after_match": True}
        self.files[relative] = proof
        return proof

    def assess(self, old, new):
        if old == new:
            return {"status": "identical", "replacements": []}
        left, right = list(self.pattern.finditer(old)), list(self.pattern.finditer(new))
        if len(left) != len(right):
            return {"status": "unexplained", "reason": "different exact-path token counts"}
        old_at = new_at = 0
        replacements = []
        for a, b in zip(left, right, strict=True):
            if old[old_at:a.start()] != new[new_at:b.start()]:
                return {"status": "unexplained", "reason": "non-path message bytes differ"}
            old_path, new_path = a.group(), b.group()
            if old_path != new_path:
                if not old_path.startswith(self.prefixes[0]) or not new_path.startswith(self.prefixes[1]):
                    return {"status": "unexplained", "reason": "path substitution has wrong roles"}
                relative = old_path[len(self.prefixes[0]):]
                if relative != new_path[len(self.prefixes[1]):]:
                    return {"status": "unexplained", "reason": "different relative source paths"}
                try:
                    proof = self.verify_file(os.fsdecode(relative))
                except (ValueError, RuntimeError) as error:
                    return {"status": "unexplained", "reason": str(error)}
                replacements.append({"old_span": [a.start(), a.end()], "new_span": [b.start(), b.end()],
                                     "old_path": os.fsdecode(old_path), "new_path": os.fsdecode(new_path),
                                     "relative": proof["relative"], "source_sha256": proof["sha256"]})
            old_at, new_at = a.end(), b.end()
        if old[old_at:] != new[new_at:]:
            return {"status": "unexplained", "reason": "remaining message bytes differ"}
        if not replacements:
            return {"status": "unexplained", "reason": "no verified checkout-path substitution"}
        return {"status": "checkout_path_only", "replacements": replacements,
                "all_residual_bytes_identical": True,
                "old_message_sha256": sha_bytes(old), "new_message_sha256": sha_bytes(new)}


def finish(config, before, strict_status):
    output = Path(config["output"])
    after = native_snapshot(config)
    json_write(output / "inputs-after.json", after)
    stable = before == after
    rows = []
    missing = []
    for index, case in enumerate(config["cases"], 1):
        path = output / "cases" / f"{index:05d}" / "comparison.json"
        if path.exists():
            rows.append(json.loads(path.read_text()))
        else:
            missing.append({"index": index, "case": case})
    strict_log = (output / "strict.log").read_bytes()
    match = re.search(rb"(?:([0-9]+) of ([0-9]+) differ|([0-9]+) programs identical)\s*$", strict_log)
    reported_count = int(match.group(2) or match.group(3)) if match else None
    reported_differences = int(match.group(1) or b"0") if match else None
    differences = sum(not row["strict_equal"] for row in rows)
    errors = [dict(case=row["case"], errors=row["validation_errors"]) for row in rows if row["validation_errors"]]
    usage_records = []
    for role in ("old", "new"):
        usage_path = output / ("usage-" + role + ".json")
        if not usage_path.exists():
            errors.append({"error": "missing compiler runtime-mode capability observation", "role": role})
        else:
            usage_records.append(json.loads(usage_path.read_text()))
    if any(record["timed_out"] for record in usage_records):
        errors.append({"error": "compiler usage/capability check timed out"})
    supports_rt = all((output / ("usage-" + role + ".msg")).exists()
                      and b"pystachy rt " in (output / ("usage-" + role + ".msg")).read_bytes()
                      for role in ("old", "new"))
    for row in rows:
        case = row["case"]
        runtime_case = case == "runtime.py" or case.endswith("/runtime.py") or ("/" in case and Path(case).name.startswith("rtmode_") and case.endswith(".py"))
        expected = "rt" if supports_rt and runtime_case else "ir"
        if row["old"]["mode"] != expected or row["new"]["mode"] != expected:
            errors.append({"error": "recorded command disagrees with oracle runtime-mode rule", "case": case})
    if not stable:
        errors.append({"error": "input source/tool manifests changed during the run"})
    if reported_count != len(config["cases"]) or reported_differences != differences:
        errors.append({"error": "recorder and unmodified oracle summary disagree",
                       "oracle_count": reported_count, "oracle_differences": reported_differences})
    if strict_status not in (0, 1) or (strict_status == 0) != (differences == 0):
        errors.append({"error": "oracle exit status disagrees with retained strict comparisons"})
    summary = {"schema": 1, "complete": not missing and not errors,
               "status": "passed" if strict_status == 0 and not missing and not errors else "failed",
               "gate_passed": strict_status == 0 and not missing and not errors,
               "strict_gate_passed": strict_status == 0,
               "strict_exit_code": strict_status, "case_count": len(config["cases"]),
               "standard_case_count": config["standard_case_count"],
               "extra_case_count": len(config["extra_cases"]), "extra_cases": config["extra_cases"],
               "recorded_cases": len(rows), "strict_differences": differences,
               "changed_statuses": sum(not row["status_equal"] for row in rows),
               "changed_diagnostics": sum(not row["messages_equal"] for row in rows),
               "changed_ir": sum(not row["ir_equal"] for row in rows),
               "ir_old_lines": sum(row["ir_line_changes"]["old_lines"] for row in rows),
               "ir_new_lines": sum(row["ir_line_changes"]["new_lines"] for row in rows),
               "missing": missing, "validation_errors": errors, "inputs_stable": stable,
               "rows": rows}
    json_write(output / "comparison.json", summary)
    proof = DiagnosticProof(config, before, after)
    assessments = []
    for row in rows:
        if row["messages_equal"]:
            continue
        directory = output / "cases" / f"{row['index']:05d}"
        result = proof.assess((directory / "old.msg").read_bytes(), (directory / "new.msg").read_bytes())
        assessments.append(dict(index=row["index"], case=row["case"], **result))
    unexplained = [row for row in assessments if row["status"] == "unexplained"]
    assessment = {"schema": 1, "strict_result_unchanged": True,
                  "strict_comparison_sha256": file_record(output / "comparison.json")["sha256"],
                  "all_diagnostics_explained": not unexplained,
                  "no_unexplained_diagnostics_or_status_changes": not unexplained and summary["changed_statuses"] == 0
                    and summary["complete"],
                  "checkout_path_only_cases": sum(row["status"] == "checkout_path_only" for row in assessments),
                  "unexplained_cases": len(unexplained), "files": proof.files, "cases": assessments,
                  "scope": "Diagnostic byte proof only; changed LLVM is not claimed equivalent or passed."}
    json_write(output / "diagnostic-assessment.json", assessment)
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, indent=2), flush=True)
    print(json.dumps({key: value for key, value in assessment.items() if key not in ("files", "cases")}, indent=2), flush=True)
    return strict_status if summary["complete"] else 2


def run(args):
    root = args.root.resolve()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("use a new output directory; previous records are immutable")
    if output.is_relative_to(root):
        raise RuntimeError("keep recording outputs outside the candidate source tree")
    old = (args.old or root / "build/ref/pystachy").resolve()
    new = (args.new or root / "pystachy").resolve()
    if new.parent != root:
        raise RuntimeError("candidate compiler must use the candidate checkout as its own home")
    controller = Path(__file__).resolve()
    for path in (old, new, controller, output, Path(sys.executable).resolve()):
        if any(character.isspace() for character in str(path)):
            raise RuntimeError("oracle command-word adapters require paths without whitespace")
    if not 1 <= args.workers <= 4:
        raise RuntimeError("workers must be between 1 and 4")
    base_ref = command(["git", "rev-parse", "--verify", args.base_ref + "^{commit}"], cwd=root).stdout.decode().strip()
    if (old.parent / "commit").read_text().strip() != base_ref:
        raise RuntimeError("reference compiler commit file does not match requested baseline")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PYSTACHY_") and key != "PYTHONPATH"}
    env.update(PYSTACHY_HOME="", PYSTACHY_PATH="", PYSTACHY_JOBS=str(args.workers),
               LC_ALL="C", LANG="C", PYTHONHASHSEED="0")
    standard_cases = oracle_cases(root, env)
    extra_cases = []
    if args.include_recursion_benchmarks:
        actual = tuple(sorted(str(path.relative_to(root)) for path in (root / "bench/recursion").glob("*.py")
                              if path.is_file()))
        if actual != RECURSION_CASES:
            raise RuntimeError(f"recursion benchmark inventory changed; review before running: {actual!r}")
        if any(case in standard_cases for case in actual):
            raise RuntimeError("recursion benchmark already occurs in the standard oracle corpus")
        extra_cases = list(actual)
    cases = standard_cases + extra_cases
    output.mkdir(parents=True)
    config = {"root": str(root), "old": str(old), "new": str(new), "output": str(output),
              "controller": str(controller), "python": str(Path(sys.executable).resolve()),
              "python_version": sys.version, "platform": platform.platform(),
              "workers": args.workers, "timeout_s": args.timeout, "base_ref": base_ref,
              "cases": cases, "standard_case_count": len(standard_cases), "standard_cases": standard_cases,
              "extra_cases": extra_cases, "include_recursion_benchmarks": args.include_recursion_benchmarks,
              "sanitized_environment": {key: env[key] for key in
                  ("PYSTACHY_HOME", "PYSTACHY_PATH", "PYSTACHY_JOBS", "LC_ALL", "LANG", "PYTHONHASHSEED")}}
    config_path = output / "config.json"
    json_write(config_path, config)
    before = native_snapshot(config)
    json_write(output / "inputs-before.json", before)
    adapters = [" ".join((config["python"], str(controller), "worker", str(config_path), role))
                for role in ("old", "new")]
    oracle = ["sh", "tools/irsame.sh", *adapters]
    if args.include_recursion_benchmarks:
        # Supplying the complete verified list changes no oracle logic. The
        # standard corpus is retained in full before the four explicit extras.
        oracle.extend(cases)
    json_write(output / "oracle-command.json", {"argv": oracle, "cwd": str(root)})
    print(f"Recording {len(cases)} exact oracle cases with {args.workers} workers", flush=True)
    started = time.monotonic()
    with (output / "strict.log").open("wb") as log:
        process = subprocess.Popen(oracle, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        while True:
            try:
                status = process.wait(timeout=20)
                break
            except subprocess.TimeoutExpired:
                count = sum(1 for _ in (output / "cases").glob("*/comparison.json"))
                print(f"Recorded {count}/{len(cases)} cases; {time.monotonic() - started:.0f}s elapsed", flush=True)
    (output / "strict-exit-status.txt").write_text(str(status) + "\n")
    print((output / "strict.log").read_text(errors="backslashreplace"), end="", flush=True)
    return finish(config, before, status)


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "worker":
        try:
            return worker(sys.argv[2], sys.argv[3], sys.argv[4:])
        except Exception as error:
            config = json.loads(Path(sys.argv[2]).read_text())
            name = "worker-error-" + str(os.getpid()) + ".json"
            json_write(Path(config["output"]) / name, {"argv": sys.argv[3:], "error": repr(error)})
            sys.stdout.buffer.write(b"corpus recording adapter failed; see its retained error record\n")
            return 125
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--old", type=Path)
    parser.add_argument("--new", type=Path)
    parser.add_argument("--base-ref", default=PINNED_BASE)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--include-recursion-benchmarks", action="store_true",
                        help="append the four checked bench/recursion programs to the complete standard oracle corpus")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
