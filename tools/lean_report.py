#!/usr/bin/env python3
"""Run every Lean check over the test corpus and write the small verification report.

The hosted compiler compiles each differential test program and deviation once
(tools/inspect_compiler.py --typed-after-only --guard-evidence), and every adapter checks that
snapshot: dynamic payload reads (check_lean_boundary), unchecked accesses (check_lean_access),
removed null checks and closed-union reads (check_lean_guards), field initialization
(check_lean_fields) and collector scanning (check_lean_gc) in every program, and promoting ints'
fit claims, inline arithmetic and storage guards (check_lean_storage) in the programs whose
imports reach a module that opts in to them. tools/lean_boundary/REPORT.md records the counts,
each function left unproved and digests of the inputs; --status compares those digests with the
checkout. A rejection is an investigation target, not by itself a compiler bug.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time

import check_lean_access as access
import check_lean_boundary as boundary
import check_lean_corpus as corpus
import check_lean_fields as fields
import check_lean_gc as gc
import check_lean_guards as guards
import check_lean_storage as storage
import check_lean_storage_corpus as storage_corpus

ROOT = corpus.ROOT
REPORT = ROOT / "tools/lean_boundary/REPORT.md"
# (one JSON line per checked program, written as each finishes: --resume continues a run)
RECORDS = ROOT / "build/lean-report.jsonl"
# (key, row title, its document, what it counts)
CHECKS = (
    ("payload", "Dynamic payload reads", "README.md", "reads"),
    ("access", "Unchecked list and dict accesses", "ACCESS.md", "accesses"),
    ("null", "Removed null checks", "GUARDS.md#removed-checks-through-memory", "removals"),
    ("union", "Closed-union reads", "GUARDS.md#coverage-of-compiled-code", "reads"),
    ("union_payload", "Union payload bits", "GUARDS.md#payload-bits-and-split-locals", "obligations"),
    ("fields", "Field initialization", "GUARDS.md#field-initialization", "obligations"),
    ("gc", "Collector scanning", "GC.md", "obligations"),
    ("int", "Promoting-int fit claims", "INT.md", "claims"),
    ("int_inline", "Promoting-int inline arithmetic", "INT.md#actual-inline-overflow-tests", "uses"),
    ("storage", "Promoting-int storage", "STORAGE.md", "obligations"),
)
# (union payload bits are proved with their function's union reads: one list names both)
LISTED_WITH = {"union_payload": "union"}
# What a report's counts are made from, as git pathspecs (a `*` also matches `/`): a change to
# any of them may change them. Helper packages of the tests live directly in tests/; this file
# only tallies and renders.
INPUTS = {
    "compiler": ("pystachy.py", "VERSION", "src", "lib"),
    "checkers": ("tools/inspect_compiler.py", "tools/check_lean_*.py", "tools/lean_boundary/*.lean",
                 "tools/lean_boundary/lakefile.toml", "tools/lean_boundary/lake-manifest.json",
                 "tools/lean_boundary/lean-toolchain"),
    "corpus": ("tests/*.py", "tests/*.path"),
}
MARK = "<!-- lean-report "
MESSAGE = 160  # characters of a reason kept in the report
LISTED = 25  # rejected functions listed per check; the record file keeps all

_verdicts = {}  # a worker's access results by normalized function (check_lean_access.check_all)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def inputs():
    """Each input group's digest (its tracked files' modes and blob ids) and whether the
    checkout has changes to it, untracked files included, that the digest does not show."""
    found = {}
    for group, specs in INPUTS.items():
        listed = git("ls-files", "--stage", "--", *specs)
        changed = git("status", "--porcelain", "--untracked-files=all", "--", *specs)
        found[group] = {"digest": hashlib.sha256(listed.encode()).hexdigest()[:16], "clean": changed == ""}
    return found


def inspect(program, timeout):
    """The typed-after snapshot of one program with guard evidence, and its SHA-256."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    path = corpus.located(program)
    if path.with_suffix(".path").is_file():
        env["PYSTACHY_PATH"] = path.with_suffix(".path").read_text().strip()
    with tempfile.TemporaryDirectory(prefix="pystachy-lean-report-") as directory:
        output = Path(directory) / "inspection"
        completed = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(path),
                                    "--output", str(output), "--typed-after-only", "--guard-evidence",
                                    "--timeout", str(timeout)], cwd=ROOT, env=env,
                                   capture_output=True, text=True, timeout=timeout + 60)
        report = json.loads((output / "report.json").read_text())
        if completed.returncode or report.get("status") != "ok":
            messages = "; ".join(d.get("message", "") for d in report.get("diagnostics", []))
            raise ValueError(f"inspection {report.get('status')}: {messages}")
        return boundary.read_snapshot(output / "typed-after.json", boundary.MAX_PROGRAM_BYTES)


def unproved(records, count, reason=("message", "error", "why")):
    """The records not accepted, each as (function, status, obligations, reason)."""
    out = []
    for record in records:
        if record.get("status") != "accepted":
            why = next((record[key] for key in reason if record.get(key)), "")
            why = why if isinstance(why, str) else json.dumps(why, sort_keys=True)
            out.append({"function": record.get("function"), "status": record.get("status"),
                        "obligations": record.get(count), "reason": " ".join(why.split())[:MESSAGE]})
    return out


def counted(functions, obligations, proved, records, count):
    return {"functions": functions, "obligations": obligations, "proved": proved,
            "unproved": unproved(records, count)}


def payload_check(snapshot, checker, _):
    report, _ = boundary.check_all(snapshot, checker)
    totals = report["totals"]
    return {"payload": counted(totals["payload_functions"], totals["reads"], totals["proved_reads"],
                               report["functions"], "reads")}


def access_check(snapshot, _, access_checker):
    report, _ = access.check_all(snapshot, access_checker, _verdicts)
    totals = report["totals"]
    return {"access": counted(totals["access_functions"], totals["accesses"], totals["proved_accesses"],
                              report["functions"], "accesses")}


def guard_checks(snapshot, checker, access_checker):
    results, contracts = fields.check_all(snapshot, checker)
    report, _ = guards.check_all(snapshot, checker, access_checker, field_results=(results, contracts))
    removals = [r for r in report["records"] if r.get("scope") == guards.REMOVALS]
    unions = [r for r in report["records"] if r.get("scope") != guards.REMOVALS]
    gc_report, _ = gc.check_all(snapshot, checker)
    return {
        "null": counted(len(removals), report["removed_checks"], report["proved_removed_checks"], removals,
                        "obligations"),
        "union": counted(len(unions), report["union_reads"], report["proved_union_reads"], unions,
                         "obligations"),
        "union_payload": counted(sum(r.get("payload_obligations", 0) > 0 for r in unions),
                                 report["payload_obligations"], report["proved_payload_obligations"], [], ""),
        "fields": counted(len(results), sum(r.get("obligations", 0) for r in results),
                          sum(r.get("obligations", 0) for r in results if r["status"] == "accepted"),
                          results, "obligations"),
        "gc": counted(gc_report["functions"], gc_report["obligations"], gc_report["proved_obligations"],
                      gc_report["records"], "obligations"),
    }


def storage_checks(snapshot, _, __):
    report, _ = storage.check_all(snapshot)
    totals = report["totals"]
    claims = report["arithmetic"]
    inline = claims["inline"]
    return {
        "int": counted(claims["totals"]["claim_functions"], claims["totals"]["claims"],
                       claims["totals"]["proved_claims"], claims["functions"], "claims"),
        "int_inline": counted(len(inline["functions"]), inline["totals"]["uses"], inline["totals"]["proved_uses"],
                              inline["functions"], "uses"),
        "storage": counted(totals["obligation_functions"], totals["obligations"], totals["proved_obligations"],
                           report["functions"], "obligations"),
    }


def check_program(program, promoting, timeout, checker, access_checker):
    """One program's record: each check's counts and unproved functions, or why none ran."""
    started = time.monotonic()
    record = {"program": program}
    try:
        snapshot, digest = inspect(program, timeout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return dict(record, error=" ".join(str(error).split())[:MESSAGE], seconds=round(time.monotonic() - started, 1))
    record.update(snapshot_sha256=digest, checks={})
    for run in (payload_check, access_check, guard_checks) + ((storage_checks,) if promoting else ()):
        try:
            record["checks"].update(run(snapshot, checker, access_checker))
        except (boundary.Unsupported, OSError, ValueError, KeyError, subprocess.SubprocessError,
                RecursionError) as error:
            record.setdefault("failed", {})[run.__name__] = " ".join(str(error).split())[:MESSAGE]
    record["seconds"] = round(time.monotonic() - started, 1)
    return record


def base(symbol):
    """A function's symbol without its specialization number (@f.name.3 is @f.name)."""
    return re.sub(r"\.\d+$", "", symbol or "")


def kind(reason):
    """A reason without the values, sites and names that make each function's own."""
    reason = re.sub(r"\[[^\]]*\]|'[^']*'|%[\w.]+|\bL?\d+(:\d+)?\b", "", reason)
    reason = re.sub(r"\s+(at|in|of|to)$", "", " ".join(reason.split()).rstrip(" :"))
    return reason or "(no reason)"


def summarize(records):
    """Totals per check; its rejected functions, each with the specializations and programs that
    have it rejected (a module's function once for every program); and its unsupported or failed
    functions by the kind of their reason."""
    checks = {}
    for key, *_ in CHECKS:
        rows = [r["checks"][key] for r in records if key in r.get("checks", {})]
        rejected, other = {}, {}
        for program in records:
            for item in program.get("checks", {}).get(key, {}).get("unproved", []):
                if item["status"] == "rejected":
                    # (a module's function, named with its module, is one function in every program
                    # that imports the module; a program's own is its program's)
                    group = base(item["function"]) if "$" in (item["function"] or "") else (
                        program["program"], base(item["function"]))
                    same = rejected.setdefault(group, {
                        "function": base(item["function"]), "programs": set(), "obligations": 0, "reasons": set()})
                    same["obligations"] += item["obligations"] or 0
                    same["reasons"].add(item["reason"])
                else:
                    same = other.setdefault((item["status"], kind(item["reason"])), {
                        "status": item["status"], "reason": kind(item["reason"]), "programs": set(), "functions": set()})
                    same["functions"].add(base(item["function"]))
                same["programs"].add(program["program"])
        checks[key] = {
            "programs": sum(row["obligations"] > 0 for row in rows),
            "functions": sum(row["functions"] for row in rows),
            "obligations": sum(row["obligations"] for row in rows),
            "proved": sum(row["proved"] for row in rows),
            "rejected": sorted(({"function": item["function"], "programs": sorted(item["programs"], key=str.encode),
                                 "obligations": item["obligations"], "reason": min(item["reasons"])}
                                for item in rejected.values()),
                               key=lambda item: (-item["obligations"], item["function"], item["programs"])),
            "other": sorted(({"status": item["status"], "reason": item["reason"], "programs": len(item["programs"]),
                              "functions": len(item["functions"])} for item in other.values()),
                            key=lambda item: (item["status"], -item["functions"], item["reason"]))}
    failed = sorted([{"program": r["program"], "reason": r["error"]} for r in records if "error" in r]
                    + [{"program": r["program"], "reason": f"{name}: {why}"}
                       for r in records for name, why in r.get("failed", {}).items()],
                    key=lambda item: item["program"].encode())
    return {"programs": len(records), "checks": checks, "failed": failed}


def number(value):
    return f"{value:,}"


def plural(count, word):
    return f"{number(count)} {word}{'' if count == 1 else 's'}"


def render(summary, meta):
    """The report's Markdown, from a summary and its metadata (commit, date, inputs)."""
    lines = ["# Lean verification report", "",
             "<!-- Generated by tools/lean_report.py (make lean-report): regenerate it, do not edit it. -->", "",
             f"Made from commit `{meta['commit']}` on {meta['date']}: the hosted compiler compiled each of the "
             f"{number(summary['programs'])} differential test programs and deviations once, and each check below "
             "ran on its typed IR. Each row's document gives its model, its trust boundary and what its known "
             "rejections are; a new rejection is an investigation target, not by itself a compiler bug. "
             f"Python {meta['python']}, {meta['lean']}; the checks took {number(meta['minutes'])} minutes of worker time.",
             "", "| Check | Programs | Functions | Proved | Rejected | Unsupported |", "|---|--:|--:|--:|--:|--:|"]
    for key, title, document, unit in CHECKS:
        row = summary["checks"][key]
        listed = summary["checks"][LISTED_WITH.get(key, key)]
        unsupported = sum(item["functions"] for item in listed["other"])
        cells = ("", "") if key in LISTED_WITH else (number(len(listed["rejected"])), number(unsupported))
        lines.append(f"| [{title}]({document}) | {number(row['programs'])} | {number(row['functions'])} | "
                     f"{number(row['proved'])} of {number(row['obligations'])} {unit} | {cells[0]} | {cells[1]} |")
    lines += ["", "Programs count those with an obligation of the check, functions those it checked in each "
              "program. Rejected and unsupported count functions, a specialization's with its function's, and "
              "union payload bits are proved with their reads; unsupported includes errors. A library function "
              "counts once however many programs compile it.", "", "## Not proved"]
    for key, title, _, unit in CHECKS:
        row = summary["checks"][key]
        if key in LISTED_WITH or not (row["rejected"] or row["other"]):
            continue
        lines += ["", f"{title}:", ""]
        for item in row["rejected"][:LISTED]:
            where = (f"`{item['programs'][0]}`" if len(item["programs"]) == 1
                     else plural(len(item["programs"]), "program"))
            lines.append(f"- `{item['function']}` in {where}, {plural(item['obligations'], unit[:-1])}: "
                         f"{item['reason']}")
        if len(row["rejected"]) > LISTED:
            lines.append(f"- and {len(row['rejected']) - LISTED} more rejected functions (the record file lists them)")
        for item in row["other"]:
            lines.append(f"- {item['status']}, {plural(item['functions'], 'function')} in "
                         f"{plural(item['programs'], 'program')}: {item['reason']}")
    lines += ["", "Programs or checks that did not complete:", ""]
    lines += [f"- `{item['program']}`: {item['reason']}" for item in summary["failed"]] or ["- none"]
    lines += ["", "## Inputs", "",
              "Digests of the tracked files each group names (`tools/lean_report.py`'s `INPUTS`); "
              "`python3.13 tools/lean_report.py --status` compares them with a checkout. Regenerate after a "
              "change to typed IR, a pass a check covers or a checker, and commit the report when it changes.",
              "", f"{MARK}{json.dumps(meta['inputs'], sort_keys=True)} -->", ""]
    for group, item in sorted(meta["inputs"].items()):
        lines.append(f"- {group}: `{item['digest']}`")
    return "\n".join(lines) + "\n"


def load(path):
    """A record file's header and its records, the last of each program's (a line a crash cut
    short is dropped)."""
    lines = path.read_text().splitlines()
    header = json.loads(lines[0])["header"] if lines else None
    boundary.require(isinstance(header, dict), f"{path} is not a lean_report record file")
    records = {}
    for index, line in enumerate(lines[1:], 2):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            boundary.require(index == len(lines), f"{path}:{index}: malformed record")
            continue
        records[record["program"]] = record
    return header, list(records.values())


def meta(header, records):
    """A report's metadata: its header, the date and the worker time its records took."""
    return dict(header, date=time.strftime("%Y-%m-%d"),
                minutes=round(sum(record.get("seconds", 0) for record in records) / 60))


def recorded(path=REPORT):
    """The input digests a report records."""
    for line in path.read_text().splitlines():
        if line.startswith(MARK) and line.endswith(" -->"):
            return json.loads(line[len(MARK):-len(" -->")])
    raise ValueError(f"{path} records no inputs")


def status(path=REPORT):
    """Print which input groups differ from the report's; 0 when none does."""
    before, now = recorded(path), inputs()
    stale = [group for group in INPUTS if before.get(group, {}).get("digest") != now[group]["digest"]
             or not now[group]["clean"]]
    for group in INPUTS:
        state = "unchanged" if group not in stale else (
            "changed" if before.get(group, {}).get("digest") != now[group]["digest"] else "uncommitted changes")
        print(f"{group}: {state}")
    return 1 if stale else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("programs", nargs="*", help="check only these (the report is then written to --output)")
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--timeout", type=float, default=300, help="seconds per inspection")
    parser.add_argument("--checker", type=Path, default=boundary.DEFAULT_CHECKER)
    parser.add_argument("--access-checker", type=Path, default=access.DEFAULT_CHECKER)
    parser.add_argument("--output", type=Path, default=REPORT, help="the Markdown report to write")
    parser.add_argument("--records", type=Path, default=RECORDS,
                        help="the record file, one JSON line per program as it finishes")
    parser.add_argument("--resume", action="store_true",
                        help="keep the record file's programs, if its inputs are the checkout's, and check the rest")
    parser.add_argument("--render", action="store_true", help="only write the report from the record file")
    parser.add_argument("--status", action="store_true", help="only compare the report's inputs with the checkout")
    parser.add_argument("--progress", action="store_true", help="print each completed program to stderr")
    args = parser.parse_args(argv)
    if args.status:
        return status(args.output)
    if args.render:
        header, records = load(args.records)
        records.sort(key=lambda record: record["program"].encode())
        args.output.write_text(render(summarize(records), meta(header, records)))
        return 0
    if args.jobs < 1 or args.timeout <= 0:
        parser.error("use at least one worker and a positive timeout")
    found = inputs()
    if args.output.resolve() == REPORT and (args.programs or not all(item["clean"] for item in found.values())):
        parser.error("the committed report needs the whole corpus and a checkout without changes to its inputs: "
                     "pass --output for another file")
    programs = args.programs or corpus.corpus()
    if len(set(programs)) != len(programs):
        parser.error("duplicate programs")
    toolchain = (ROOT / "tools/lean_boundary/lean-toolchain").read_text().strip()
    header = {"commit": git("rev-parse", "--short=12", "HEAD").strip(), "python": platform.python_version(),
              "lean": "Lean " + toolchain.rsplit(":v", 1)[-1],
              "inputs": {group: {"digest": item["digest"]} for group, item in found.items()}}
    records = []
    if args.resume and args.records.is_file():
        previous, records = load(args.records)
        if {key: previous.get(key) for key in ("python", "lean", "inputs")} != {
                key: header[key] for key in ("python", "lean", "inputs")}:
            parser.error(f"{args.records} was made from other inputs: run without --resume")
        header, wanted = previous, set(programs)
        records = [record for record in records if record["program"] in wanted]
    else:
        args.records.parent.mkdir(parents=True, exist_ok=True)
        args.records.write_text(json.dumps({"header": header}, sort_keys=True) + "\n")
    checked = {record["program"] for record in records}
    remaining = [program for program in programs if program not in checked]
    promoting = set(storage_corpus.select(remaining))
    # (processes: a thread holds the interpreter while it checks a snapshot)
    context = multiprocessing.get_context("forkserver")
    with args.records.open("a") as output, concurrent.futures.ProcessPoolExecutor(
            args.jobs, mp_context=context) as pool:
        work = [pool.submit(check_program, program, program in promoting, args.timeout, args.checker,
                            args.access_checker) for program in remaining]
        for done in concurrent.futures.as_completed(work):
            records.append(done.result())
            output.write(json.dumps(records[-1], sort_keys=True) + "\n")
            output.flush()
            if args.progress:
                print(f"{len(records)}/{len(programs)} {records[-1]['program']} {records[-1]['seconds']}s",
                      file=sys.stderr, flush=True)
    if inputs() != found:
        raise SystemExit("the report's inputs changed while it ran: run it again")
    records.sort(key=lambda record: record["program"].encode())
    summary = summarize(records)
    args.output.write_text(render(summary, meta(header, records)))
    print(json.dumps({key: {k: v if isinstance(v, int) else len(v) for k, v in row.items()}
                      for key, row in summary["checks"].items()}, sort_keys=True))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
