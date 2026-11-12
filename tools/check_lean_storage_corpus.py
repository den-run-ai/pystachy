#!/usr/bin/env python3
"""Prove promoting-int storage guards in every test whose imports reach python-int.

Unlike a textual pragma search, selection follows imports and NAME.path using the
same conservative traversal as the dynamic-Any corpus. No failed inspection,
unsupported function, or uninventoried obligation counts as a proof.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import check_lean_boundary as boundary
import check_lean_corpus as corpus
import check_lean_storage as storage
from src.pystachy_compiler.diagnostics import int_pragma

ROOT = corpus.ROOT
COUNTS = ("functions", "obligation_functions", "low_word_uses", "tail_reads", "boundaries",
          "stack_copy_reads", "stack_copy_obligations",
          "obligations", "proved_obligations", "proof_batches", "unclassified_functions",
          "accepted", "rejected", "unsupported", "error")


def select(programs=None):
    reach = corpus.Reach(pragma=int_pragma)
    return [program for program in (corpus.corpus() if programs is None else programs)
            if reach.dynamic(corpus.located(program), corpus.search_path(corpus.located(program)))]


def check_program(program, checker, timeout):
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    path = corpus.located(program)
    if path.with_suffix(".path").is_file():
        env["PYSTACHY_PATH"] = path.with_suffix(".path").read_text().strip()
    started = time.monotonic()
    record = {"program": program}
    try:
        with tempfile.TemporaryDirectory(prefix="pystachy-lean-storage-") as directory:
            output = Path(directory) / "inspection"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(path),
                 "--output", str(output), "--typed-after-only", "--timeout", str(timeout)],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout + 60)
            report = json.loads((output / "report.json").read_text())
            boundary.require(completed.returncode == 0 and report.get("status") == "ok",
                             f"inspection failed: {report.get('diagnostics', [])}")
            snapshot, digest = boundary.read_snapshot(output / "typed-after.json", boundary.MAX_PROGRAM_BYTES)
        compiled = time.monotonic()
        fields, _ = storage.check_all(snapshot, checker)
        return dict(record, status=fields["status"], snapshot_sha256=digest, totals=fields["totals"],
                    functions=fields["functions"],
                    failures=[fn for fn in fields["functions"] if fn["status"] != "accepted"],
                    arithmetic=fields.get("arithmetic", {}),
                    seconds={"inspection": round(compiled - started, 2),
                             "lean": round(time.monotonic() - compiled, 2)})
    except (OSError, ValueError, subprocess.SubprocessError, RecursionError) as error:
        return dict(record, status="error", message=str(error))


def summarize(records, seconds):
    worst = max((record["status"] for record in records), key=boundary.SEVERITY.index, default="error")
    totals = {key: sum(record.get("totals", {}).get(key, 0) for record in records) for key in COUNTS}
    totals.update(programs=len(records), failed_programs=sum(r["status"] != "accepted" for r in records))
    # A vanished inventory is a broken gate, even if every remaining function is vacuous.
    if worst == "accepted" and totals["obligations"] == 0:
        worst = "unsupported"
    if worst == "accepted" and (totals["unclassified_functions"] or
                                totals["proved_obligations"] != totals["obligations"]):
        worst = "error"
    return {"status": worst, "totals": totals, "programs": records, "seconds": round(seconds, 1),
            "scope": "promoting-int storage guards of test programs and their imports",
            "limitations": storage.LIMITATIONS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("programs", nargs="*", help="check these programs instead of selecting the corpus")
    parser.add_argument("--checker", type=Path, default=storage.DEFAULT_CHECKER)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--report", type=Path, help="write a new JSON report")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--progress", action="store_true", help="print each completed program to stderr")
    args = parser.parse_args(argv)
    if not 1 <= args.jobs <= 8 or not 0 < args.timeout <= 600:
        parser.error("--jobs must be 1..8 and --timeout must be positive and at most 600")
    programs = args.programs or select()
    if args.list:
        print("\n".join(programs))
        return 0
    if not args.checker.is_file():
        print(f"check_lean_storage_corpus: missing Lean checker: {args.checker}", file=sys.stderr)
        return 3
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        pending = {pool.submit(check_program, program, args.checker, args.timeout): index
                   for index, program in enumerate(programs)}
        indexed = {}
        for future in concurrent.futures.as_completed(pending):
            record = future.result()
            indexed[pending[future]] = record
            if args.progress:
                print(f"{len(indexed)}/{len(programs)} {record['status']}: {record['program']}",
                      file=sys.stderr, flush=True)
        records = [indexed[index] for index in range(len(programs))]
    report = summarize(records, time.monotonic() - started)
    if args.report:
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, sort_keys=True, indent=1)
            output.write("\n")
    for record in records:
        if record["status"] != "accepted":
            print(f"{record['status']}: {record['program']}: {record.get('message', '')}")
            for failure in record.get("failures", []):
                print(f"  {failure['status']}: {failure['function']}: {failure.get('message', '')}")
            for failure in record.get("arithmetic", {}).get("functions", []):
                if failure["status"] != "accepted":
                    print(f"  arithmetic {failure['status']}: {failure['function']}: {failure.get('message', '')}")
    totals = report["totals"]
    print(f"check_lean_storage_corpus: {report['status']}: {totals['programs']} programs, "
          f"{totals['proved_obligations']} of {totals['obligations']} obligations proved "
          f"({report['seconds']} s)")
    return boundary.OUTCOMES[report["status"]]


if __name__ == "__main__":
    sys.exit(main())
