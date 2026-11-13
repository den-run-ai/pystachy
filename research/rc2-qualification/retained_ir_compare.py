#!/usr/bin/env python3
"""Retain an exact native-compiler corpus comparison without sharing compiler homes.

Only the old checkout's exact byte prefix is replaced with the equal-length new
prefix, on a separate comparison copy. Raw evidence is never rewritten. This is
an IR/diagnostic comparison, not native execution or complete release validation.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time


INVENTORY_SHELL = """for f in pystachy.py runtime.py tests/programs/*/*.py tests/deviations/*.py bench/*.py bench/pyperformance/*.py tests/ir/*.py tests/errors/*/*.py; do
  [ ! -f "$f" ] || printf '%s\\n' "$f"
done"""


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def source_manifest(root: Path) -> dict[str, str]:
    # Include every tracked file, not just the selected inputs. This captures the
    # compiler, libraries, helper modules, sidecars and relevant build metadata.
    names = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z"]
    ).decode().split("\0")
    result = {}
    for name in names:
        if name and (root / name).is_file():
            result[name] = sha_file(root / name)
    return result


def tree_info(root: Path, expected: str) -> dict[str, object]:
    head = git(root, "rev-parse", "HEAD")
    if head != expected:
        raise RuntimeError(f"{root}: expected {expected}, found {head}")
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise RuntimeError(f"{root}: source checkout is not clean:\n{status}")
    binary = root / "pystachy"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"{binary}: native compiler is missing or not executable")
    return {
        "root": str(root),
        "commit": head,
        "tree": git(root, "rev-parse", "HEAD^{tree}"),
        "binary": str(binary),
        "binary_sha256": sha_file(binary),
        "binary_size": binary.stat().st_size,
        "git_status": status,
    }


def read_output(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def output_info(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False}
    return {"exists": True, "bytes": path.stat().st_size, "sha256": sha_file(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--llvm", help="Optional explicit matching LLVM directory")
    args = parser.parse_args()
    base, candidate, output = args.base.resolve(), args.candidate.resolve(), args.output.resolve()
    old_prefix, new_prefix = str(base).encode(), str(candidate).encode()
    if base == candidate or len(old_prefix) != len(new_prefix):
        raise RuntimeError("Use distinct checkout roots with exactly equal byte lengths")
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite prior evidence: {output}")
    if output.is_relative_to(base) or output.is_relative_to(candidate):
        raise RuntimeError("Evidence must be outside both source checkouts")
    diff_executable = shutil.which("diff")
    if diff_executable is None:
        raise RuntimeError("The standard diff utility is required to retain byte-preserving diffs")
    roots = {"base": base, "candidate": candidate}
    source = {
        "base": tree_info(base, args.base_sha),
        "candidate": tree_info(candidate, args.candidate_sha),
    }
    manifests = {side: source_manifest(root) for side, root in roots.items()}
    output.mkdir(parents=True)
    (output / "cases").mkdir()
    for side in roots:
        json_write(output / f"{side}-source-manifest.json", manifests[side])
    environment = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    environment["LC_ALL"] = "C"
    environment["PYSTACHY_IRCHECK"] = "1"
    environment["PYSTACHY_JOBS"] = "1"
    environment.pop("PYTHONPATH", None)
    if args.llvm:
        environment["PYSTACHY_LLVM"] = args.llvm
    inventory = subprocess.check_output(
        ["sh", "-c", INVENTORY_SHELL], cwd=candidate, env=environment, text=True
    ).splitlines()
    if not inventory or len(set(inventory)) != len(inventory):
        raise RuntimeError("Empty or duplicate corpus inventory")
    runtime_mode = {}
    for side, root in roots.items():
        env = dict(environment, PYSTACHY_HOME=str(root), PYSTACHY_PATH="")
        probe = subprocess.run(
            [str(root / "pystachy")], cwd=candidate, env=env,
            capture_output=True, timeout=15,
        )
        runtime_mode[side] = b"pystachy rt " in probe.stdout + probe.stderr
        (output / f"{side}-usage.stdout").write_bytes(probe.stdout)
        (output / f"{side}-usage.stderr").write_bytes(probe.stderr)
        version = subprocess.run(
            [str(root / "pystachy"), "--version"], cwd=candidate, env=env,
            capture_output=True, timeout=15,
        )
        source[side]["version_status"] = version.returncode
        source[side]["version_stdout"] = version.stdout.decode(errors="replace")
        source[side]["version_stderr"] = version.stderr.decode(errors="replace")
    if not all(runtime_mode.values()):
        raise RuntimeError(f"Both native compilers must advertise runtime mode: {runtime_mode}")
    inv_rows = []
    for index, case in enumerate(inventory):
        inputs = {case: sha_file(candidate / case)}
        for suffix in (".path", ".in", ".out", ".err", ".full"):
            path = Path(case).with_suffix(suffix)
            if (candidate / path).exists():
                inputs[str(path)] = sha_file(candidate / path)
        mode = "rt" if case == "runtime.py" or Path(case).name.startswith("rtmode_") else "ir"
        inv_rows.append({"index": index, "case": case, "mode": mode, "inputs": inputs})
    json_write(output / "inventory.json", inv_rows)
    metadata = {
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "source_manifest_sha256": {
            side: sha_file(output / f"{side}-source-manifest.json") for side in roots
        },
        "inventory_sha256": sha_file(output / "inventory.json"),
        "script_sha256": sha_file(Path(__file__).resolve()),
        "cwd": str(candidate),
        "workers": args.workers,
        "timeout_per_compiler_seconds": args.timeout,
        "environment": {
            k: v for k, v in environment.items()
            if k.startswith("PYSTACHY_") or k == "LC_ALL"
        },
        "machine": platform.platform(),
        "normalization": {
            "operation": "base bytes.replace(exact_base_root, exact_candidate_root); candidate unchanged",
            "base_prefix": str(base), "candidate_prefix": str(candidate),
            "prefix_bytes": len(old_prefix),
            "other_normalizations": [],
        },
        "raw_retention": "stdout/stderr/IR plus fixture files for every raw difference or infrastructure error",
        "corpus_count": len(inventory),
    }
    json_write(output / "metadata.json", metadata)
    started = time.monotonic()

    def compare(row: dict[str, object]) -> dict[str, object]:
        index, case, mode = int(row["index"]), str(row["case"]), str(row["mode"])
        directory = output / "cases" / f"{index:05d}"
        directory.mkdir()
        result = {"index": index, "case": case, "mode": mode, "directory": str(directory)}
        import_path = ""
        if (candidate / Path(case).with_suffix(".path")).exists():
            prep = subprocess.run(
                ["sh", "tests/prepare_path.sh", case, str(directory)],
                cwd=candidate, env=environment, capture_output=True, timeout=15,
            )
            result["prepare_path"] = {
                "status": prep.returncode,
                "stdout": prep.stdout.decode(errors="replace"),
                "stderr": prep.stderr.decode(errors="replace"),
            }
            if prep.returncode:
                result["classification"] = "infrastructure_error"
                json_write(directory / "result.json", result)
                return result
            import_path = prep.stdout.decode().rstrip("\n")
        result["import_path"] = import_path
        statuses = {}
        errors = []
        for side, root in roots.items():
            command = [str(root / "pystachy"), mode, case, "-o", str(directory / f"{side}.ll")]
            env = dict(environment, PYSTACHY_HOME=str(root), PYSTACHY_PATH=import_path)
            begin = time.monotonic()
            with (directory / f"{side}.stdout").open("wb") as stdout, (directory / f"{side}.stderr").open("wb") as stderr:
                try:
                    run = subprocess.run(command, cwd=candidate, env=env, stdout=stdout, stderr=stderr, timeout=args.timeout)
                    status: int | str = run.returncode
                except subprocess.TimeoutExpired:
                    status = "timeout"
                except OSError as error:
                    status = "spawn_error"
                    errors.append(f"{side}: {error}")
            statuses[side] = status
            result[side] = {
                "command": command, "status": status,
                "elapsed_seconds": round(time.monotonic() - begin, 6),
                "outputs": {kind: output_info(directory / f"{side}.{kind}") for kind in ("stdout", "stderr", "ll")},
            }
        raw_equal = statuses["base"] == statuses["candidate"]
        normal_equal = raw_equal
        substitutions = {}
        parts = []
        for kind in ("stdout", "stderr", "ll"):
            before, after = read_output(directory / f"base.{kind}"), read_output(directory / f"candidate.{kind}")
            raw_equal = raw_equal and before == after
            normalized = None if before is None else before.replace(old_prefix, new_prefix)
            normal_equal = normal_equal and normalized == after
            substitutions[kind] = 0 if before is None else before.count(old_prefix)
            if normalized != after:
                parts.append(kind)
        abnormal = [side for side, status in statuses.items() if status not in (0, 1)]
        classification = "infrastructure_error" if errors or abnormal else "identical" if raw_equal else "path_only" if normal_equal else "material_difference"
        result.update({
            "classification": classification,
            "raw_equal": raw_equal, "normalized_equal": normal_equal,
            "normalization_substitutions": substitutions,
            "material_output_parts": parts,
            "new_rejection": statuses["base"] == 0 and statuses["candidate"] != 0,
            "new_acceptance": statuses["base"] != 0 and statuses["candidate"] == 0,
            "errors": errors, "abnormal_statuses": abnormal,
        })
        if classification == "identical":
            shutil.rmtree(directory)
            result["directory"] = None
        else:
            for kind in ("stdout", "stderr", "ll"):
                before, after = read_output(directory / f"base.{kind}"), read_output(directory / f"candidate.{kind}")
                normalized = None if before is None else before.replace(old_prefix, new_prefix)
                if normalized is not None:
                    (directory / f"base.normalized.{kind}").write_bytes(normalized)
                if normalized != after:
                    with (directory / f"{kind}.diff").open("wb") as diff_output:
                        diff_run = subprocess.run(
                            [diff_executable, "-u",
                             str(directory / f"base.normalized.{kind}") if normalized is not None else "/dev/null",
                             str(directory / f"candidate.{kind}") if after is not None else "/dev/null"],
                            stdout=diff_output, stderr=subprocess.PIPE,
                        )
                    if diff_run.returncode not in (0, 1):
                        raise RuntimeError(f"{case}: failed to retain {kind} diff: {diff_run.stderr!r}")
            json_write(directory / "result.json", result)
        return result

    results = []
    with (output / "results.jsonl").open("w") as log:
        with ThreadPoolExecutor(max_workers=args.workers) as workers:
            futures = {workers.submit(compare, row): row for row in inv_rows}
            for future in as_completed(futures):
                row = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    result = {"index": row["index"], "case": row["case"], "classification": "infrastructure_error", "errors": [repr(error)]}
                results.append(result)
                log.write(json.dumps(result, sort_keys=True) + "\n")
                log.flush()
                if len(results) % 100 == 0 or len(results) == len(inv_rows):
                    print(json.dumps({"completed": len(results), "total": len(inv_rows), "counts": dict(Counter(r["classification"] for r in results)), "elapsed_seconds": round(time.monotonic() - started, 1)}), flush=True)
    results.sort(key=lambda row: int(row["index"]))
    json_write(output / "results.json", results)
    end_sources = {side: source_manifest(root) for side, root in roots.items()}
    source_changes = {side: [name for name in sorted(set(manifests[side]) | set(end_sources[side])) if manifests[side].get(name) != end_sources[side].get(name)] for side in roots}
    end_identity = {side: tree_info(root, str(source[side]["commit"])) for side, root in roots.items()}
    binary_changed = {side: source[side]["binary_sha256"] != end_identity[side]["binary_sha256"] for side in roots}
    counts = Counter(row["classification"] for row in results)
    differences = [row for row in results if row["classification"] != "identical"]
    summary = {
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "expected_count": len(inv_rows), "completed_count": len(results),
        "classification_counts": dict(counts),
        "base_status_counts": dict(Counter(str(row.get("base", {}).get("status", "missing")) for row in results)),
        "candidate_status_counts": dict(Counter(str(row.get("candidate", {}).get("status", "missing")) for row in results)),
        "new_rejections": [row["case"] for row in results if row.get("new_rejection")],
        "new_acceptances": [row["case"] for row in results if row.get("new_acceptance")],
        "material_differences": [row["case"] for row in results if row["classification"] == "material_difference"],
        "path_only": [row["case"] for row in results if row["classification"] == "path_only"],
        "infrastructure_errors": [row for row in results if row["classification"] == "infrastructure_error"],
        "source_changes_during_run": source_changes,
        "binary_changed_during_run": binary_changed,
        "complete_and_stable": len(results) == len(inv_rows) and not counts["infrastructure_error"] and not any(source_changes.values()) and not any(binary_changed.values()),
        "semantic_adjudication": "pending: every material difference requires review",
    }
    json_write(output / "summary.json", summary)
    json_write(output / "differences.json", differences)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("material_differences", "path_only", "infrastructure_errors")}, indent=2), flush=True)
    print(f"Evidence: {output}", flush=True)
    return 2 if not summary["complete_and_stable"] else 1 if counts["material_difference"] or summary["new_rejections"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
