#!/usr/bin/env python3
"""Inventory and check guard obligations in every differential/deviation program.

Selection is the complete test corpus, not source-text heuristics or opt-in
pragmas. Unsupported obligations remain in the denominator and cause failure.
"""
import argparse
import concurrent.futures
import functools
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import check_lean_boundary as boundary
import check_lean_corpus as corpus
import check_lean_fields as fields
import check_lean_gc as gc
import check_lean_guards as guards

ROOT = Path(__file__).resolve().parent.parent
COUNT_KEYS = ("union_reads", "removed_checks", "proved_union_reads", "proved_removed_checks")
# Obligations on union payload bits beyond inventoried reads (check_lean_guards.normalize).
PAYLOAD_KEYS = ("payload_obligations", "proved_payload_obligations")
# Field initialization of objects under construction (check_lean_fields).
FIELD_KEYS = ("field_obligations", "proved_field_obligations")
# Uses of lists, dicts and sets whose arrays the collector must scan (check_lean_gc).
GC_KEYS = ("gc_obligations", "proved_gc_obligations")


def failed(program, error):
    return dict.fromkeys(COUNT_KEYS) | {"program": program, "status": "error",
                                       "error": error, "inventory_complete": False}


def validate_record(record):
    boundary.require(all(key in record for key in COUNT_KEYS), "guard record missing obligation counts")
    complete = record.get("inventory_complete")
    boundary.require(type(complete) is bool, "missing inventory completeness")
    if complete:
        boundary.require(all(type(record[key]) is int and record[key] >= 0 for key in COUNT_KEYS),
                         "invalid guard obligation counts")
        boundary.require(record["proved_union_reads"] <= record["union_reads"]
                         and record["proved_removed_checks"] <= record["removed_checks"], "proved counts exceed inventory")
    else:
        boundary.require(record["status"] == "error" and all(record[key] is None for key in COUNT_KEYS),
                         "partial inventory must be an explicit uncounted error")
    if complete and any(key in record for key in PAYLOAD_KEYS):
        boundary.require(all(type(record.get(key)) is int and record[key] >= 0 for key in PAYLOAD_KEYS)
                         and record["proved_payload_obligations"] <= record["payload_obligations"],
                         "invalid payload obligation counts")
    if complete and any(key in record for key in FIELD_KEYS):
        boundary.require(all(type(record.get(key)) is int and record[key] >= 0 for key in FIELD_KEYS)
                         and record["proved_field_obligations"] <= record["field_obligations"],
                         "invalid field obligation counts")
    if complete and any(key in record for key in GC_KEYS):
        boundary.require(all(type(record.get(key)) is int and record[key] >= 0 for key in GC_KEYS)
                         and record["proved_gc_obligations"] <= record["gc_obligations"],
                         "invalid collector obligation counts")
    if record["status"] == "accepted":
        boundary.require(complete and record["union_reads"] == record["proved_union_reads"]
                         and record["removed_checks"] == record["proved_removed_checks"]
                         and record.get("payload_obligations", 0) == record.get("proved_payload_obligations", 0)
                         and record.get("field_obligations", 0) == record.get("proved_field_obligations", 0)
                         and record.get("gc_obligations", 0) == record.get("proved_gc_obligations", 0),
                         "accepted record omitted obligations")


def summarize(programs, records, seconds):
    boundary.require(programs and len(records) == len(programs)
                     and [r["program"] for r in records] == programs, "incomplete guard program inventory")
    for record in records:
        validate_record(record)
    status = max((r["status"] for r in records), key=boundary.SEVERITY.index)
    counts = {key: sum(r[key] for r in records if r["inventory_complete"]) for key in COUNT_KEYS}
    counts.update({key: sum(r.get(key, 0) for r in records if r["inventory_complete"])
                   for key in PAYLOAD_KEYS + FIELD_KEYS + GC_KEYS})
    counts.update({key: sum(r["status"] == key for r in records) for key in boundary.SEVERITY})
    counts["programs"] = len(records)
    counts["uninventoried_programs"] = sum(not r["inventory_complete"] for r in records)
    counts["vacuous_programs"] = sum(r["status"] == "accepted" and r["inventory_complete"]
                                     and r["union_reads"] == 0 and r["removed_checks"] == 0
                                     and r.get("payload_obligations", 0) == 0
                                     and r.get("field_obligations", 0) == 0
                                     and r.get("gc_obligations", 0) == 0 for r in records)
    return {"status": status, "totals": counts, "programs": records,
            "inventory_complete": counts["uninventoried_programs"] == 0,
            "seconds": seconds, "limitations": guards.LIMITATIONS, "field_limitations": fields.LIMITATIONS,
            "gc_limitations": gc.LIMITATIONS}


def check_program(program, checker, timeout):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    path = corpus.located(program)
    sidecar = path.with_suffix(".path")
    if sidecar.is_file():
        env["PYSTACHY_PATH"] = sidecar.read_text().strip()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=".pystachy-guard-corpus-") as temporary:
        output = Path(temporary) / "inspection"
        try:
            completed = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(path),
                                        "--output", str(output), "--typed-after-only", "--guard-evidence",
                                        "--timeout", str(timeout)], cwd=ROOT, env=env,
                                       capture_output=True, text=True, timeout=timeout + 30)
            if completed.returncode:
                report = json.loads((output / "report.json").read_text())
                return failed(program, report.get("diagnostics", []))
            snapshot, digest = boundary.read_snapshot(output / "typed-after.json", boundary.MAX_PROGRAM_BYTES)
            field_results, contracts = fields.check_all(snapshot, checker)
            report, _ = guards.check_all(snapshot, checker, field_results=(field_results, contracts))
            field_report = fields.program_report(field_results)
            gc_report, _ = gc.check_all(snapshot, checker)
            gc_counts = {"gc_status": gc_report["status"], "gc_obligations": gc_report["obligations"],
                         "proved_gc_obligations": gc_report["proved_obligations"],
                         "unproved_gc_functions": [r for r in gc_report["records"] if r["status"] != "accepted"]}
            status = max(report["status"], field_report["field_status"], gc_report["status"], key=boundary.SEVERITY.index)
            return dict(report, **field_report, **gc_counts, status=status, program=program, inventory_complete=True,
                        snapshot_sha256=digest, seconds=round(time.monotonic() - started, 2))
        except (ValueError, KeyError, OSError, subprocess.SubprocessError, RecursionError) as error:
            return failed(program, str(error))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("programs", nargs="*")
    parser.add_argument("--checker", type=Path, default=boundary.DEFAULT_CHECKER)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--progress", action="store_true", help="print each completed program to stderr")
    args = parser.parse_args(argv)
    if not 1 <= args.jobs <= 2 or args.timeout <= 0:
        parser.error("use one or two workers and a positive timeout")
    programs = args.programs or corpus.corpus()
    if not programs:
        parser.error("guard corpus inventory is empty")
    if len(set(programs)) != len(programs):
        parser.error("duplicate programs")
    if args.list:
        print("\n".join(programs))
        return 0
    started = time.monotonic()
    # (worker processes: a thread holds the interpreter while it checks a snapshot, which is most
    # of a program's time)
    context = multiprocessing.get_context("forkserver")
    with concurrent.futures.ProcessPoolExecutor(args.jobs, mp_context=context) as pool:
        records = []
        for record in pool.map(functools.partial(check_program, checker=args.checker, timeout=args.timeout), programs):
            records.append(record)
            if args.progress:
                print(f"{len(records)}/{len(programs)} {record['status']} {record['program']}", file=sys.stderr, flush=True)
    summary = summarize(programs, records, round(time.monotonic() - started, 1))
    status = summary["status"]
    if args.report:
        with args.report.open("x") as output:
            json.dump(summary, output, indent=1, sort_keys=True)
            output.write("\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "programs"}, sort_keys=True))
    return boundary.OUTCOMES[status]


if __name__ == "__main__":
    raise SystemExit(main())
