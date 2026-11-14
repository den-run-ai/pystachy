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

Each worker process forks a child to compile each program, with the compiler it imported once.
Workers share, in an SQLite table, the results of checks that a library's functions repeat across
programs: Lean's result for each candidate and the access model's for each normalized function
(Shared). Each value is computed from its key's content alone, so no record depends on which worker
checked which program, or in what order.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import gc
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import re
import select
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback

import check_lean_access as access
import check_lean_boundary as boundary
import check_lean_corpus as corpus
import check_lean_fields as fields
import check_lean_gc as collector
import check_lean_guards as guards
import check_lean_storage as storage
import check_lean_storage_corpus as storage_corpus
import inspect_compiler

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
# any of them may change them. Helper packages of the tests live directly in tests/; the runner
# selects checks and controls compilation, so it is an input too.
INPUTS = {
    "compiler": ("pystachy.py", "VERSION", "src", "lib"),
    "checkers": ("tools/lean_report.py", "tools/inspect_compiler.py", "tools/check_lean_*.py", "tools/lean_boundary/*.lean",
                 "tools/lean_boundary/lakefile.toml", "tools/lean_boundary/lake-manifest.json",
                 "tools/lean_boundary/lean-toolchain"),
    "corpus": ("tests/*.py", "tests/*.path"),
}
MARK = "<!-- lean-report "
MESSAGE = 160  # characters of a reason kept in the report
LISTED = 25  # rejected functions listed per check; the record file keeps all

_verdicts = {}  # access results by normalized function (check_lean_access.check_all; a worker's: Shared)


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


def clean_inputs(found):
    """Only explicit clean provenance makes index digests safe to reuse."""
    return (isinstance(found, dict) and set(found) == set(INPUTS)
            and all(isinstance(found[group], dict) and found[group].get("clean") is True for group in INPUTS))


def checker_executables(checker, access_checker):
    """The actual executables, including custom ones, whose verdicts a run may reuse."""
    found = {}
    for kind, value in (("boundary", checker), ("access", access_checker)):
        path = Path(value).resolve()
        found[kind] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return found


def inspect(program, timeout):
    """The typed-after snapshot of one program with guard evidence, and its SHA-256: what
    `tools/inspect_compiler.py PROGRAM --typed-after-only --guard-evidence` writes, but compiled by
    its worker in a child of this process (compiled)."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    # (inspect_compiler's run_worker checks the IR it compiles)
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_IRCHECK="1")
    path = corpus.located(program)
    if path.with_suffix(".path").is_file():
        env["PYSTACHY_PATH"] = path.with_suffix(".path").read_text().strip()
    with tempfile.TemporaryDirectory(prefix="pystachy-lean-report-") as directory:
        output = Path(directory)
        code = compiled(path, output, env, timeout)
        if not (output / "report.json").is_file():
            raise ValueError(f"inspection error: the compilation exited {code} without a report")
        report = json.loads((output / "report.json").read_text())
        if code or report.get("status") != "ok":
            messages = "; ".join(d.get("message", "") for d in report.get("diagnostics", []))
            raise ValueError(f"inspection {report.get('status')}: {messages}")
        # (parsing JSON makes no reference cycles, but the collector, tracing the objects it
        # makes, took half the time)
        collecting = gc.isenabled()
        gc.disable()
        try:
            return boundary.read_snapshot(output / "typed-after.json", boundary.MAX_PROGRAM_BYTES)
        finally:
            if collecting:
                gc.enable()


def compiled(path, output, env, timeout):
    """Run inspect_compiler's worker, as `inspect_compiler.py --_worker` does, on path into the
    directory output, in a child forked from this process: it imported the compiler once, so no
    program starts Python and imports it again, and each still compiles in a process of its own.
    The child's exit status; past timeout seconds it is killed."""
    from src.pystachy_compiler import diagnostics, driver  # noqa: F401 (the child's compiler)
    arguments = argparse.Namespace(source=str(path.absolute()), output=str(output), function="",
                                   typed_after_only=True, guard_evidence=True)
    done, finished = os.pipe()  # (finished closes when the child exits)
    gc.freeze()  # (the child's collections then leave this process's objects and their pages alone)
    child = os.fork()
    if child == 0:
        code = 2
        try:
            os.close(done)
            os.chdir(ROOT)
            os.environ.clear()
            os.environ.update(env)
            os.dup2(os.open(os.devnull, os.O_RDWR), 0)
            os.dup2(0, 1)
            os.dup2(os.open(output / "worker.stderr", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644), 2)
            # (a compilation allocates millions of objects that reference counting frees: at its
            # default thresholds, the collector took a fifth of a large program's compilation;
            # the child exits after one, with no more memory at its peak)
            gc.set_threshold(100000, 50, 100)
            code = inspect_compiler.worker(arguments)
        except BaseException:
            traceback.print_exc()
        finally:
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            finally:
                os._exit(code)
    gc.unfreeze()
    os.close(finished)
    try:
        if not select.select([done], [], [], timeout)[0]:
            os.kill(child, signal.SIGKILL)
            os.waitpid(child, 0)
            raise subprocess.TimeoutExpired(str(path), timeout)
        return os.waitstatus_to_exitcode(os.waitpid(child, 0)[1])
    finally:
        os.close(done)


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
    report, _ = access.check_all(snapshot, access_checker, _verdicts, guards.snapshot_effects(snapshot))
    totals = report["totals"]
    return {"access": counted(totals["access_functions"], totals["accesses"], totals["proved_accesses"],
                              report["functions"], "accesses")}


def guard_checks(snapshot, checker, access_checker):
    results, contracts = fields.check_all(snapshot, checker)
    report, _ = guards.check_all(snapshot, checker, access_checker, field_results=(results, contracts))
    removals = [r for r in report["records"] if r.get("scope") == guards.REMOVALS]
    unions = [r for r in report["records"] if r.get("scope") != guards.REMOVALS]
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
    }


def gc_check(snapshot, checker, _):
    report, _ = collector.check_all(snapshot, checker)
    return {"gc": counted(report["functions"], report["obligations"], report["proved_obligations"],
                          report["records"], "obligations")}


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


class Shared(dict):
    """Results a run's workers share: in this process's memory and as rows of an SQLite database
    (made by main), so that a library's function one worker checked is not checked again by
    another. A key is the content its value is computed from alone (a checker and its input), so
    whichever worker computes a value computes the same one."""

    def __init__(self, database, kind):
        super().__init__()
        self.kind = kind
        self.connection = sqlite3.connect(database, timeout=600, isolation_level=None)
        self.connection.execute("PRAGMA synchronous=OFF")

    def __getitem__(self, key):
        if not dict.__contains__(self, key):
            row = self.connection.execute("SELECT value FROM results WHERE key = ?",
                                          (self.kind + repr(key),)).fetchone()
            if row is None:
                raise KeyError(key)
            dict.__setitem__(self, key, json.loads(row[0]))
        return dict.__getitem__(self, key)

    def __contains__(self, key):
        return self.get(key) is not None

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self.connection.execute("INSERT OR IGNORE INTO results VALUES (?, ?)",
                                (self.kind + repr(key), json.dumps(value, sort_keys=True)))


def keep_results(database):
    """A worker's caches, shared with the run's other workers: access results by normalized
    function (check_lean_access.check_all), access-model attempts of removed checks
    (check_lean_guards.prove_removals) and Lean's results by candidate
    (check_lean_boundary.checker_result)."""
    global _verdicts
    _verdicts = Shared(database, "access")
    guards._removal_attempts = Shared(database, "removals")
    boundary.RESULTS = Shared(database, "lean")


def results_database(path):
    """A new database for Shared: one table of each result by its kind and key."""
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE results (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.close()
    return str(path)


def checked_records(args, programs, promoting, database):
    """The same checks and per-run caches, with no pool for one worker. Spawn is available
    where forkserver's Unix socket cannot be created; each compilation still owns its child."""
    global _verdicts
    if args.jobs == 1:
        previous = _verdicts, guards._removal_attempts, boundary.RESULTS
        keep_results(database)
        try:
            for program in programs:
                yield check_program(program, program in promoting, args.timeout, args.checker, args.access_checker)
        finally:
            for cache in (_verdicts, guards._removal_attempts, boundary.RESULTS):
                cache.connection.close()
            _verdicts, guards._removal_attempts, boundary.RESULTS = previous
        return
    context = multiprocessing.get_context(args.start_method)
    with concurrent.futures.ProcessPoolExecutor(args.jobs, mp_context=context, initializer=keep_results,
                                               initargs=(database,)) as pool:
        work = [pool.submit(check_program, program, program in promoting, args.timeout, args.checker,
                            args.access_checker) for program in programs]
        for done in concurrent.futures.as_completed(work):
            yield done.result()


def check_program(program, promoting, timeout, checker, access_checker):
    """One program's record: each check's counts and unproved functions, or why none ran."""
    started = time.monotonic()
    record = {"program": program}
    try:
        snapshot, digest = inspect(program, timeout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return dict(record, error=" ".join(str(error).split())[:MESSAGE], seconds=round(time.monotonic() - started, 1))
    record.update(snapshot_sha256=digest, checks={}, timing={"inspect": round(time.monotonic() - started, 2)})
    for run in (payload_check, access_check, guard_checks, gc_check) + ((storage_checks,) if promoting else ()):
        begun = time.monotonic()
        try:
            record["checks"].update(run(snapshot, checker, access_checker))
        except (boundary.Unsupported, OSError, ValueError, KeyError, subprocess.SubprocessError,
                RecursionError) as error:
            record.setdefault("failed", {})[run.__name__] = " ".join(str(error).split())[:MESSAGE]
        record["timing"][run.__name__] = round(time.monotonic() - begun, 2)
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
              "Only records made from clean inputs can be resumed. Dirty experimental inputs and older "
              "records without clean provenance cannot certify a clean checkout.",
              "", f"{MARK}{json.dumps(meta['inputs'], sort_keys=True)} -->", ""]
    for group, item in sorted(meta["inputs"].items()):
        note = "" if item.get("clean") is True else (
            " (uncommitted inputs)" if item.get("clean") is False else " (clean provenance not recorded)")
        lines.append(f"- {group}: `{item['digest']}`{note}")
    return "\n".join(line.rstrip() for line in lines) + "\n"


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
             or not clean_inputs(before) or not now[group]["clean"]]
    for group in INPUTS:
        state = "unchanged" if group not in stale else (
            "changed" if before.get(group, {}).get("digest") != now[group]["digest"] else
            "uncommitted changes" if not now[group]["clean"] else "report lacks clean input provenance")
        print(f"{group}: {state}")
    return 1 if stale else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("programs", nargs="*", help="check only these (the report is then written to --output)")
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--start-method", choices=("forkserver", "spawn"), default="forkserver",
                        help="process start method with --jobs greater than one (default: forkserver)")
    parser.add_argument("--timeout", type=float, default=300, help="seconds per inspection")
    parser.add_argument("--checker", type=Path, default=boundary.DEFAULT_CHECKER)
    parser.add_argument("--access-checker", type=Path, default=access.DEFAULT_CHECKER)
    parser.add_argument("--output", type=Path, default=REPORT, help="the Markdown report to write")
    parser.add_argument("--records", type=Path, default=RECORDS,
                        help="the record file, one JSON line per program as it finishes")
    parser.add_argument("--resume", action="store_true",
                        help="reuse clean-input records matching this clean checkout, and check the rest")
    parser.add_argument("--render", action="store_true", help="only write the report from the record file")
    parser.add_argument("--status", action="store_true", help="only compare the report's inputs with the checkout")
    parser.add_argument("--progress", action="store_true", help="print each completed program to stderr")
    args = parser.parse_args(argv)
    if args.status:
        return status(args.output)
    if args.render:
        if args.output.resolve() == REPORT:
            parser.error("--render needs --output for another file; generate the committed report "
                         "with a full run or a validated --resume")
        header, records = load(args.records)
        records.sort(key=lambda record: record["program"].encode())
        args.output.write_text(render(summarize(records), meta(header, records)))
        return 0
    if args.jobs < 1 or args.timeout <= 0:
        parser.error("use at least one worker and a positive timeout")
    found = inputs()
    if args.output.resolve() == REPORT and (args.programs or not clean_inputs(found)):
        parser.error("the committed report needs the whole corpus and a checkout without changes to its inputs: "
                     "pass --output for another file")
    programs = args.programs or corpus.corpus()
    if len(set(programs)) != len(programs):
        parser.error("duplicate programs")
    toolchain = (ROOT / "tools/lean_boundary/lean-toolchain").read_text().strip()
    try:
        executables = checker_executables(args.checker, args.access_checker)
    except OSError as error:
        parser.error(f"cannot read checker executable: {error}")
    header = {"commit": git("rev-parse", "--short=12", "HEAD").strip(), "python": platform.python_version(),
              "lean": "Lean " + toolchain.rsplit(":v", 1)[-1],
              "checker_executables": executables,
              "inputs": found}
    records = []
    if args.resume and args.records.is_file():
        previous, records = load(args.records)
        # Index digests do not identify dirty working contents. Even an unchanged
        # dirty run cannot be resumed, and old headers omitted this provenance.
        if not clean_inputs(previous.get("inputs", {})) or not clean_inputs(found):
            parser.error(f"{args.records} lacks matching clean input provenance: run without --resume")
        if {key: previous.get(key) for key in ("python", "lean", "inputs", "checker_executables")} != {
                key: header[key] for key in ("python", "lean", "inputs", "checker_executables")}:
            parser.error(f"{args.records} was made from other inputs: run without --resume")
        header, wanted = previous, set(programs)
        records = [record for record in records if record["program"] in wanted]
    else:
        args.records.parent.mkdir(parents=True, exist_ok=True)
        args.records.write_text(json.dumps({"header": header}, sort_keys=True) + "\n")
    checked = {record["program"] for record in records}
    remaining = [program for program in programs if program not in checked]
    promoting = set(storage_corpus.select(remaining))
    with tempfile.TemporaryDirectory(prefix="pystachy-lean-report-") as shared, \
            args.records.open("a") as output:
        database = results_database(Path(shared) / "results.db")
        for record in checked_records(args, remaining, promoting, database):
            records.append(record)
            output.write(json.dumps(records[-1], sort_keys=True) + "\n")
            output.flush()
            if args.progress:
                print(f"{len(records)}/{len(programs)} {records[-1]['program']} {records[-1]['seconds']}s",
                      file=sys.stderr, flush=True)
    if inputs() != found:
        raise SystemExit("the report's inputs changed while it ran: run it again")
    if checker_executables(args.checker, args.access_checker) != executables:
        raise SystemExit("the checker executables changed while the report ran: run it again")
    records.sort(key=lambda record: record["program"].encode())
    summary = summarize(records)
    args.output.write_text(render(summary, meta(header, records)))
    print(json.dumps({key: {k: v if isinstance(v, int) else len(v) for k, v in row.items()}
                      for key, row in summary["checks"].items()}, sort_keys=True))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
