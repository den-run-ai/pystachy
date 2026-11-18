#!/usr/bin/env python3
"""Check every dyn.payload read and unchecked access of the dynamic-Any test programs with Lean.

The corpus is each differential program and deviation (tests/corpus.sh) that opts in to dynamic
Any, or that reaches through its imports a module that does, on the search path the compiler
gives it: its directory, its NAME.path directories, then lib/. Each is compiled by the hosted
compiler under tools/inspect_compiler.py --typed-after-only. tools/check_lean_boundary.py
checks every function of its snapshot that reads a dynamic payload, and tools/check_lean_access.py
every function with an unchecked list read or dict entry. Exit 0 when Lean accepts them all, 1
when it rejects one, 2 when one is outside the supported abstraction, 3 when a program does not
compile or a snapshot is malformed.
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import check_lean_access as access
import check_lean_boundary as bridge

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler.diagnostics import dynamic_pragma  # noqa: E402

PATTERNS = ("tests/programs/*/*.py", "tests/deviations/*.py")


def corpus():
    return sorted((path.relative_to(ROOT).as_posix() for pattern in PATTERNS for path in ROOT.glob(pattern)
                   if path.is_file()), key=lambda name: name.encode())


def located(program):
    # (a corpus program is named relative to the checkout)
    return Path(program) if Path(program).is_absolute() else ROOT / program


def search_path(path):
    """The directories the compiler searches for the imports of the program at path, in order
    (driver.py); the tests' NAME.path entries are relative to the checkout."""
    directories = [path.parent]
    sidecar = path.with_suffix(".path")
    if sidecar.is_file():
        directories += [ROOT / entry for entry in sidecar.read_text().strip().split(":") if entry]
    return directories + [ROOT / "lib"]


class Reach:
    """Which files a program may compile: the modules its imports name, in each directory of
    its search path that has them, with the __init__.py of every package on the way. An import
    in any branch or function counts, as does a name imported from a package that is also its
    submodule: over-approximate, so that no program that compiles dynamic code is left out."""

    def __init__(self, pragma=dynamic_pragma):
        self.parsed = {}
        self.pragma = pragma

    def facts(self, path):
        # (opts in, its imports: (level, dotted module parts, imported names))
        if path not in self.parsed:
            raw = path.read_bytes()
            # The compiler's pragma recognizer sees Latin-1-decoded source bytes,
            # including a UTF-8 BOM as three characters. Keep that same input.
            text = raw.decode("latin-1")
            try:
                tree = ast.parse(raw)  # (bytes: a byte-order mark or coding line is the source's)
            except SyntaxError:
                # (an unparsable file is compiled anyway: keep the program in the corpus)
                self.parsed[path] = (True, [])
                return self.parsed[path]
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports += [(0, alias.name.split("."), []) for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imports.append((node.level, node.module.split(".") if node.module else [],
                                    [alias.name for alias in node.names if alias.name != "*"]))
            self.parsed[path] = (self.pragma(text), imports)
        return self.parsed[path]

    @staticmethod
    def files(directories, parts, namespaces=None):
        # In each directory, each package's __init__.py from the top, then the module itself.
        # As loader.py's filepath finds them, NAME/__init__.py comes before NAME.py, and a
        # directory without either is a portion of a namespace package, which has no code.
        found = []
        for directory in directories:
            base = directory
            for index, part in enumerate(parts):
                if (base / part / "__init__.py").is_file():
                    base = base / part
                    found.append(base / "__init__.py")
                elif (base / (part + ".py")).is_file():
                    if index == len(parts) - 1:
                        found.append(base / (part + ".py"))
                    break
                elif (base / part).is_dir():
                    base = base / part
                    if namespaces is not None:
                        namespaces.add(base)
                else:
                    break
        return found

    def dynamic(self, path, directories):
        """Whether the file at path, or a module it reaches on directories, opts in."""
        pending, seen = [path], set()
        while pending:
            path = pending.pop()
            if path in seen:
                continue
            seen.add(path)
            opted, imports = self.facts(path)
            if opted:
                return True
            for level, parts, names in imports:
                # (a relative import starts from the importing file's package)
                bases = directories if level == 0 else [path.parents[level - 1]]
                for module in [parts] + [parts + [name] for name in names]:
                    if module:
                        pending += self.files(bases, module)
        return False


def select(programs=None):
    """The programs, by default the corpus's, that may compile dynamic code."""
    reach = Reach()
    return [program for program in (corpus() if programs is None else programs)
            if reach.dynamic(located(program), search_path(located(program)))]


def check_program(program, checker, timeout, access_checker=access.DEFAULT_CHECKER, verdicts=None):
    """Inspect one program and check its snapshot. A record: its status, counts and failures.
    verdicts: the access checker's results by function, which programs that share a library
    function reuse (check_lean_access.check_all). Unprefixed status counters count payload
    functions; access_<status> counters count access functions. A function can count in both."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    path = located(program)
    sidecar = path.with_suffix(".path")
    if sidecar.is_file():
        env["PYSTACHY_PATH"] = sidecar.read_text().strip()
    record = {"program": program}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=".pystachy-lean-corpus-") as temporary:
        output = Path(temporary) / "inspection"
        try:
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(path),
                 "--output", str(output), "--typed-after-only", "--timeout", str(timeout)],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout + 60)
            report = json.loads((output / "report.json").read_text())
            if completed.returncode != 0 or report.get("status") != "ok":
                messages = [d.get("message", "") for d in report.get("diagnostics", [])]
                return dict(record, status="error", message=f"inspection {report.get('status')}: "
                                                            + "; ".join(messages)[:500])
            snapshot, digest = bridge.read_snapshot(output / "typed-after.json", bridge.MAX_PROGRAM_BYTES)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            return dict(record, status="error", message=f"inspection failed: {error}")
    compiled = time.monotonic()
    try:
        fields, _ = bridge.check_all(snapshot, checker)
        accessed = time.monotonic()
        accesses, _ = access.check_all(snapshot, access_checker, verdicts)
    except (OSError, ValueError, subprocess.SubprocessError, RecursionError) as error:
        return dict(record, status="error", message=str(error))
    failures = [function for function in fields["functions"] + accesses["functions"]
                if function["status"] != "accepted"]
    status = max(fields["status"], accesses["status"], key=bridge.SEVERITY.index)
    totals = dict(fields["totals"], **{key: accesses["totals"][key] for key in
                                      ("access_functions", "accesses", "proved_accesses")})
    totals.update({"access_" + status: accesses["totals"][status] for status in bridge.SEVERITY})
    return dict(record, status=status, snapshot_sha256=digest, totals=totals, failures=failures,
                seconds={"inspection": round(compiled - started, 2), "lean": round(accessed - compiled, 2),
                         "access": round(time.monotonic() - accessed, 2)})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("programs", nargs="*", help="programs to check, all of them, instead of the selected corpus")
    parser.add_argument("--checker", type=Path, default=bridge.DEFAULT_CHECKER)
    parser.add_argument("--access-checker", type=Path, default=access.DEFAULT_CHECKER)
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--timeout", type=float, default=600.0, help="seconds per inspection")
    parser.add_argument("--report", type=Path, help="write the full JSON report to this new file")
    parser.add_argument("--list", action="store_true", help="only print the selected programs")
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    programs = args.programs or select()
    if args.list:
        print("\n".join(programs))
        return 0
    for checker in (args.checker, args.access_checker):
        if not checker.is_file():
            print(f"check_lean_corpus: no Lean checker at {checker}; run make check-lean-boundary",
                  file=sys.stderr)
            return 3
    started = time.monotonic()
    verdicts = {}
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        records = list(pool.map(lambda program: check_program(program, args.checker, args.timeout,
                                                              args.access_checker, verdicts), programs))
    worst = max((record["status"] for record in records), key=bridge.SEVERITY.index, default="accepted")
    totals = {key: sum(record.get("totals", {}).get(key, 0) for record in records)
              for key in ("functions", "payload_functions", "reads", "proved_reads",
                          "access_functions", "accesses", "proved_accesses",
                          "accepted", "unsupported", "rejected", "error",
                          "access_accepted", "access_unsupported", "access_rejected", "access_error")}
    totals["programs"] = len(records)
    totals["failed_programs"] = sum(record["status"] != "accepted" for record in records)
    inventory_errors = []
    if not records:
        inventory_errors.append("empty program inventory")
    if not args.programs and (not totals["reads"] or not totals["accesses"]):
        inventory_errors.append("default corpus lost its payload or access obligations")
    if worst == "accepted" and (totals["proved_reads"] != totals["reads"] or
                                totals["proved_accesses"] != totals["accesses"]):
        inventory_errors.append("accepted report has unproved obligations")
    if inventory_errors:
        worst = "error"
    summary = {"status": worst, "totals": totals, "seconds": round(time.monotonic() - started, 1),
               "programs": records, "inventory_errors": inventory_errors,
               "scope": "dyn.payload guards and unchecked accesses of the dynamic-Any test programs",
               "limitations": bridge.LIMITATIONS + access.LIMITATIONS}
    if args.report:
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(summary, output, indent=1, sort_keys=True)
            output.write("\n")
    for record in records:
        if record["status"] != "accepted":
            print(f"{record['status']}: {record['program']}: {record.get('message', '')}")
            for function in record.get("failures", []):
                print(f"  {function['status']}: {function['function']}: {function.get('message', '')}")
    for message in inventory_errors:
        print(f"error: {message}")
    print(f"check_lean_corpus: {worst}: {totals['programs']} programs, {totals['payload_functions']} "
          f"functions reading payloads, {totals['proved_reads']} of {totals['reads']} reads proved; "
          f"{totals['proved_accesses']} of {totals['accesses']} unchecked accesses proved "
          f"({summary['seconds']} s)")
    return bridge.OUTCOMES[worst]


if __name__ == "__main__":
    sys.exit(main())
