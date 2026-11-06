"""Research ThinLTO importing after splitting a frozen compiler module.

Example (LLVM 18, x86-64 Linux; all destinations must be new):
  python bench/compiler_host/partition_import.py --snapshot /tmp/snapshot \
    --source-root /tmp/frozen-source --llvm /opt/llvm/bin --partitions 4 \
    --jobs 4 --work /tmp/import-build --report /tmp/import-build.json

The snapshot contains linked.bc, raw.ll and seed-rt.ll. Every rebuilt compiler
must reproduce both IR witnesses. Extra --execution-samples measure only this
compiler; use run.py for interleaved comparisons with other compiler hosts.

The default prepares summaries without optimizing each partition first.
--prelink o2 explicitly tests LLVM's normal ThinLTO pre-link O2 pipeline.
That variant promotes linkonce definitions to weak before per-partition O2:
after splitting, other partitions may reference an otherwise unused definition.
llvm-lto2 supplies importing and bounded backend threads; clang performs the
native link. No LLD installation is needed. This is a self-compiler experiment,
not a general ELF linker or an arbitrary-program driver option. Module/nonempty
assembly, common/TLS/indirect symbols, cross-partition COMDAT groups and pys_new
symbols need additional contracts. The runtime's empty inline-asm pointer
barrier is accepted unchanged: its symbol reference is an ordinary LLVM operand.
Single linkonce definitions and ordinary weak
resolution are supported. Default-visible definitions are kept conservatively;
hidden definitions can be internalized. These policies affect optimization.

The backend timing includes preflight, splitting, summary generation, symbol
resolution, optimization/codegen, native linking and saved import/optimized
bitcode. IR inspection and compiler execution are reported separately. Workers
are bounded by CPU count only, with no fleet memory budget, cache or transport.
Tool hashes do not identify the complete sysroot or shared-library closure.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import re
import shlex
import statistics
import sys
import time

from backend_workers import Commands
from run import ROOT, atomic_json, bootstrap, measure, sha


TOOLS = ("clang", "opt", "llvm-split", "llvm-lto2", "llvm-dis")
INPUTS = ("linked.bc", "raw.ll", "seed-rt.ll")
HARNESS_FILES = ("bench/compiler_host/partition_import.py", "bench/compiler_host/backend_workers.py",
                 "bench/compiler_host/run.py", "bench/compiler_parallel/llvm_partitions.py",
                 "tools/bootstrap_pipeline.py")
FLAGS = re.compile(r"([DHP][U-][C-][W-][I-][O-][T-][X-]) (.+)")
QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"')
LINKONCE = re.compile(r'^(define\s+|@(?:[-a-zA-Z$._0-9]+|"(?:[^"\\]|\\.)*")\s*=\s*)'
                      r'linkonce(_odr)?(?=\s)')
# runtime.c hide(Thrower *f): __asm__("" : "+r"(f)). The empty template
# cannot mention another symbol; one ordinary ptr operand exposes the reference
# to LLVM. Keep the instruction and its constraints untouched. No general asm
# parsing or relaxation of module/nonempty-template assembly is intended.
POINTER_BARRIER = re.compile(
    r'[ \t]+%[-a-zA-Z$._0-9]+[ \t]*=[ \t]*(?:tail[ \t]+)?call[ \t]+ptr[ \t]+'
    r'asm[ \t]+"",[ \t]+"=r,0,~\{dirflag\},~\{fpsr\},~\{flags\}"'
    r'\(ptr(?:[ \t]+nonnull)?[ \t]+[@%][-a-zA-Z$._0-9]+\)'
    r'(?:[ \t]+#[0-9]+)?(?:,[ \t]*![-a-zA-Z$._0-9]+[ \t]+![0-9]+)*'
    r'[ \t]*(?:;[^\n]*)?\n?')


def parse_symtab(text):
    """Read LLVM 18 llvm-lto2's fixed flag columns; reject unknown records."""
    header, symbols = {}, []
    for line in text.splitlines():
        if not line:
            continue
        match = FLAGS.fullmatch(line)
        if match:
            flags, name = match.groups()
            if any(c in name for c in ",\r\n\t\0 "):
                raise ValueError(f"unsupported symbol spelling: {name!r}")
            symbols.append({"name": name, "flags": flags})
        elif line.startswith("         "):
            if not symbols:
                raise ValueError("orphan symbol metadata")
            key, _, value = line.strip().partition(" ")
            if key not in ("comdat", "section", "size") or key in symbols[-1]:
                raise ValueError(f"unsupported symbol metadata: {line}")
            symbols[-1][key] = value
        else:
            key, separator, value = line.partition(":")
            if (not separator or key not in ("version", "producer", "target triple",
                                              "source filename", "dependent libraries")
                    or key in header):
                raise ValueError(f"unsupported symbol table record: {line}")
            header[key] = value.strip()
    if header.get("version") != "3" or not header.get("producer", "").startswith("18."):
        raise ValueError("this experiment requires LLVM 18 symbol tables")
    if not re.fullmatch(r"x86_64-[^-]+-linux-gnu", header.get("target triple", "")):
        raise ValueError("this experiment supports x86-64 GNU/Linux ELF only")
    if header.get("dependent libraries") != "":
        raise ValueError("dependent libraries require a real linker resolution")
    return {"header": header, "symbols": symbols}


def symbol_resolutions(tables):
    """Resolve only the ELF subset produced by splitting one linked module.

    Strong definitions prevail over weak ones; otherwise the first weak
    definition in deterministic partition order prevails. A prevailing hidden
    definition uses 'pl', a visible definition 'plx'. Other references to a
    definition in this executable use 'l' (and conservatively 'x' if visible).
    Undefined library symbols get an empty resolution and reach the native link.
    LLVM's splitter keeps each COMDAT in one partition; mixed groups are rejected.
    """
    occurrences, groups = defaultdict(list), defaultdict(set)
    triples = {table["header"]["target triple"] for _, table in tables}
    if len(triples) != 1:
        raise ValueError("partition target triples differ")
    for index, (filename, table) in enumerate(tables):
        if not filename or any(c in filename for c in ",\r\n\0"):
            raise ValueError("unsupported bitcode filename in symbol resolution")
        seen = set()
        for symbol in table["symbols"]:
            name, flags = symbol["name"], symbol["flags"]
            if name in seen:
                raise ValueError(f"duplicate symbol-table entry: {name}")
            seen.add(name)
            if name == "pys_new":
                raise ValueError("pys_new needs the driver's post-O2 allocator contract")
            if flags[2] == "C" or flags[4] == "I" or flags[6] == "T":
                raise ValueError(f"common, indirect or TLS symbol is unsupported: {name}")
            if "comdat" in symbol:
                kind, _, group = symbol["comdat"].partition(" ")
                if kind != "any" or not group:
                    raise ValueError(f"unsupported COMDAT selection for {name}")
                if flags[1] != "U":
                    groups[group].add(index)
            occurrences[name].append((index, symbol))
    if any(len(partitions) != 1 for partitions in groups.values()):
        raise ValueError("COMDAT spans partitions; use a real linker resolution")
    resolutions, counts = {}, Counter()
    for name, uses in occurrences.items():
        definitions = [(i, s) for i, s in uses if s["flags"][1] != "U"]
        strong = [(i, s) for i, s in definitions if s["flags"][3] != "W"]
        if len(strong) > 1:
            raise ValueError(f"multiple strong definitions: {name}")
        if not definitions:
            if any(s["flags"][0] != "D" for _, s in uses):
                raise ValueError(f"unresolved nondefault-visible symbol: {name}")
            counts["external_symbols"] += 1
            for i, _ in uses:
                resolutions[i, name] = ""
            continue
        winner = (strong or definitions)[0][0]
        visible = any(s["flags"][0] != "H" for _, s in uses)
        counts["visible_definitions" if visible else "hidden_definitions"] += 1
        counts["weak_definitions"] += sum(s["flags"][3] == "W" for _, s in definitions)
        for i, s in uses:
            prevailing = i == winner and s["flags"][1] != "U"
            resolutions[i, name] = ("p" if prevailing else "") + "l" + ("x" if visible else "")
    main = occurrences.get("main", [])
    if not any(s["flags"][1] != "U" and s["flags"][7] == "X" for _, s in main):
        raise ValueError("a defined main function is required")
    argv = []
    for i, (filename, table) in enumerate(tables):
        for symbol in table["symbols"]:
            name = symbol["name"]
            argv += ["-r", f"{filename},{name},{resolutions[i, name]}"]
    return argv, dict(counts)


def inspect_ir(path, reject_assembly=False):
    counts = {"function_definitions": 0, "available_externally_definitions": 0,
              "linkonce_definitions": 0, "empty_pointer_barriers": 0,
              "bytes": path.stat().st_size}
    with path.open() as stream:
        for line in stream:
            if "asm" in line:
                barrier = POINTER_BARRIER.fullmatch(line)
                counts["empty_pointer_barriers"] += bool(barrier)
                # Compiler string constants can contain LLVM source, including
                # '@pys_new(' or 'asm'. Examine syntax outside quoted strings.
                if reject_assembly:
                    syntax = QUOTED.sub('""', line).split(";", 1)[0]
                    if re.search(r"(?:^|\s)asm(?:\s|$)", syntax) and not barrier:
                        raise ValueError("assembly requires a real linker resolution")
            if line.startswith("define "):
                counts["function_definitions"] += 1
                counts["available_externally_definitions"] += "available_externally" in line.split("@", 1)[0]
            counts["linkonce_definitions"] += bool(LINKONCE.match(line))
    return counts


def preserve_linkonce(source, destination):
    """Keep split-away definitions alive until the ThinLTO link knows all uses.

    This only strengthens linkonce/ODR emission to weak/ODR; it changes neither
    initializer nor body. Matching starts at definition headers, never in an
    embedded compiler string, attribute, comment or quoted global name.
    """
    promoted = 0
    with source.open() as incoming, destination.open("x") as outgoing:
        for line in incoming:
            match = LINKONCE.match(line)
            if match:
                promoted += 1
                line = match[1] + "weak" + (match[2] or "") + line[match.end():]
            outgoing.write(line)
    return promoted


def write_response(path, argv):
    # LLVM's GNU response-file tokenizer accepts POSIX shell quoting. No shell
    # executes this file; one quoted argument per line also handles large inputs.
    path.write_text("\n".join(shlex.quote(arg) for arg in argv) + "\n")


def tool_identity(llvm):
    return {name: {"path": str((llvm / name).resolve()), "sha256": sha(llvm / name)}
            for name in TOOLS}


def harness_identity():
    python = Path(sys.executable).resolve()
    return {"files": {name: sha(ROOT / name) for name in HARNESS_FILES},
            "python": {"path": str(python), "sha256": sha(python)}}


def validate_paths(snapshot, root, work, report):
    if work.exists() or work.is_symlink():
        raise ValueError("work directory must be new")
    if report.exists() or report.is_symlink():
        raise ValueError("report destination must be new")
    if report == work or report.is_relative_to(work):
        raise ValueError("report must be outside the private work directory")
    for protected in (snapshot, root):
        if work.is_relative_to(protected) or protected.is_relative_to(work):
            raise ValueError("work must not overlap the snapshot or frozen source")
        if report.is_relative_to(protected) or protected.is_relative_to(report):
            raise ValueError("report must not overlap the snapshot or frozen source")
    for name in INPUTS:
        if not (snapshot / name).is_file():
            raise ValueError(f"missing snapshot input: {name}")


def validate_settings(partitions, jobs, prelink, timeout):
    if not 1 <= partitions <= 8 or not 1 <= jobs <= 8:
        raise ValueError("require 1..8 partitions and 1..8 workers")
    if prelink not in ("summary", "o2"):
        raise ValueError("prelink must be summary or o2")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")


def backend_job(job_path, inherited_group=False):
    """Child process: the parent measures the whole backend's CPU and RSS."""
    job = json.loads(job_path.read_text())
    work, llvm, source = job_path.parent, Path(job["llvm"]), Path(job["input"])
    validate_settings(job["partitions"], job["jobs"], job["prelink"], job["timeout"])
    if job["version"] != 2 or sha(source) != job["input_sha256"]:
        raise ValueError("backend input or job version mismatch")
    if tool_identity(llvm) != job["tools"]:
        raise ValueError("backend tool identity mismatch")
    if harness_identity() != job["harness"]:
        raise ValueError("backend harness identity mismatch")
    if set(work.iterdir()) != {job_path}:
        raise ValueError("backend job directory must contain only the new job")
    report = {"version": 2, "job_sha256": sha(job_path), "steps": [], "complete": False}
    runner = Commands(measure, owns_group=not inherited_group)
    env = dict(os.environ, LC_ALL="C")
    report_path = work / "build.json"

    def execute(stage, command):
        result = runner.execute(command, env, job["timeout"], cwd=work)
        result["stage"] = stage
        report["steps"].append(result)
        atomic_json(report_path, report)
        measure.successful(result)
        return result

    try:
        with runner:
            execute("preflight", [str(llvm / "llvm-dis"), str(source), "-o", "input.ll"])
            report["input_ir"] = inspect_ir(work / "input.ll", reject_assembly=True)
            execute("split", [str(llvm / "llvm-split"), str(source), "-j", str(job["partitions"]),
                              "-o", "raw-part-"])
            pipeline = "verify" if job["prelink"] == "summary" else "thinlto-pre-link<O2>"
            parts = [f"raw-part-{i}" for i in range(job["partitions"])]
            if job["prelink"] == "o2" and report["input_ir"]["linkonce_definitions"]:
                report["linkonce_promoted"] = []
                for i, part in enumerate(parts):
                    execute("preserve_linkonce", [str(llvm / "llvm-dis"), part, "-o", f"pre-part-{i}.ll"])
                    prepared = work / f"prepared-part-{i}.ll"
                    report["linkonce_promoted"].append(preserve_linkonce(work / f"pre-part-{i}.ll", prepared))
                    parts[i] = prepared.name
            commands = [(i, [str(llvm / "opt"), f"-passes={pipeline}", "-module-summary",
                             part, "-o", f"part-{i}.bc"])
                        for i, part in enumerate(parts)]
            for result in runner.run(commands, env, job["timeout"], jobs=job["jobs"], cwd=work):
                result["stage"] = "summary"
                report["steps"].append(result)
                atomic_json(report_path, report)
                measure.successful(result)
            tables = []
            for i in range(job["partitions"]):
                filename = f"part-{i}.bc"
                result = execute("symbols", [str(llvm / "llvm-lto2"), "dump-symtab", filename])
                symbol_file = work / f"part-{i}.symbols.txt"
                symbol_file.write_text(result["stdout"])
                tables.append((filename, parse_symtab(result["stdout"])))
                # Large compiler symbol tables stay in files, not repeated in
                # every checkpoint's command/result arrays. Keep their hashes.
                result["stdout_file"] = str(symbol_file)
                result["stdout"] = ""
            resolutions, report["resolution_counts"] = symbol_resolutions(tables)
            argv = ["-O2", "-relocation-model=pic", f"-thinlto-threads={job['jobs']}",
                    f"-threads={job['jobs']}", "-select-save-temps=import,opt", "-o", "thin.o",
                    *(name for name, _ in tables), *resolutions]
            response = work / "thin.rsp"
            write_response(response, argv)
            report["response_sha256"] = sha(response)
            execute("thinlto", [str(llvm / "llvm-lto2"), "run", "@thin.rsp"])
            # Empty partitions may be omitted or enter the regular-LTO slot 0.
            # Only numeric outputs are native objects; saved bitcode is excluded.
            objects = sorted((p for p in work.glob("thin.o.*") if p.name[7:].isdigit()),
                             key=lambda p: int(p.name[7:]))
            if not objects or any(int(p.name[7:]) > job["partitions"] for p in objects):
                raise RuntimeError("unexpected ThinLTO object inventory")
            for path in objects:
                with path.open("rb") as stream:
                    if stream.read(4) != b"\x7fELF":
                        raise RuntimeError("ThinLTO output is not an ELF object")
            execute("link", [str(llvm / "clang"), *(p.name for p in objects), "-o", "compiler", "-lm"])
            report["objects"] = [{"file": p.name, "sha256": sha(p), "bytes": p.stat().st_size} for p in objects]
            report["compiler_sha256"] = sha(work / "compiler")
            report["compiler_bytes"] = (work / "compiler").stat().st_size
            report["complete"] = True
    except BaseException as exc:
        report["error"] = str(exc)
        raise
    finally:
        report["commands"] = runner.results
        atomic_json(report_path, report)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--backend-job":
        parser = argparse.ArgumentParser(description="Internal backend process")
        parser.add_argument("--backend-job", type=Path, required=True)
        parser.add_argument("--inherited-group", action="store_true")
        child = parser.parse_args(argv)
        backend_job(child.backend_job.resolve(), child.inherited_group)
        return 0
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--llvm", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--partitions", type=int, default=4)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--prelink", choices=("summary", "o2"), default="summary")
    parser.add_argument("--execution-samples", type=int, default=0)
    parser.add_argument("--cpu", type=int, help="pin frontend witnesses and execution samples to this CPU")
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args(argv)
    snapshot, root = args.snapshot.resolve(), args.source_root.resolve()
    work, llvm, destination = args.work.resolve(), args.llvm.resolve(), args.report.resolve()
    try:
        validate_paths(snapshot, root, work, destination)
        validate_settings(args.partitions, args.jobs, args.prelink, args.timeout)
        if args.execution_samples < 0:
            raise ValueError("execution sample count must be nonnegative")
        if args.cpu is not None and args.cpu < 0:
            raise ValueError("frontend CPU must be nonnegative")
    except ValueError as exc:
        parser.error(str(exc))
    source, inputs = bootstrap.source_identity(root), {name: sha(snapshot / name) for name in INPUTS}
    tools, harness = tool_identity(llvm), harness_identity()
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env.update(PYSTACHY_HOME=str(root), PYSTACHY_LLVM=str(llvm), PYTHONHASHSEED="0", LC_ALL="C")
    work.mkdir(parents=True, exist_ok=False)
    backend = work / "backend"
    backend.mkdir()
    job_path = backend / "job.json"
    atomic_json(job_path, {"version": 2, "llvm": str(llvm), "tools": tools, "harness": harness,
                          "input": str(snapshot / "linked.bc"), "input_sha256": inputs["linked.bc"],
                          "partitions": args.partitions, "jobs": args.jobs,
                          "prelink": args.prelink, "timeout": args.timeout})
    report = {"schema_version": 2, "source": source, "source_root": str(root), "inputs": inputs,
              "tools": tools, "harness": harness, "host": bootstrap.host_state(),
              "harness_sha256": sha(Path(__file__)),
              "settings": {key: getattr(args, key) for key in
                           ("partitions", "jobs", "prelink", "timeout", "cpu", "execution_samples")},
              "witnesses": {}, "execution": [], "inspection": [], "complete": False}
    runner = Commands(measure)
    started = time.monotonic()
    try:
        with runner:
            result = runner.execute([sys.executable, str(Path(__file__).resolve()), "--backend-job",
                                     str(job_path), "--inherited-group"], env, args.timeout)
            report["backend"] = result
            if (backend / "build.json").exists():
                report["build"] = json.loads((backend / "build.json").read_text())
            atomic_json(destination, report)
            measure.successful(result)
            build = report["build"]
            if (not build["complete"] or build["job_sha256"] != sha(job_path)
                    or build["compiler_sha256"] != sha(backend / "compiler")):
                raise RuntimeError("backend publication does not match its job")
            for path in sorted(backend.glob("thin.o.*.bc")):
                # Saved import/opt IR quantifies the extra scope and emitted size.
                output = path.with_suffix(".ll")
                result = runner.execute([str(llvm / "llvm-dis"), str(path), "-o", str(output)], env, args.timeout)
                measure.successful(result)
                report["inspection"].append({"file": path.name, "sha256": sha(path),
                                              "bitcode_bytes": path.stat().st_size,
                                              "ir": inspect_ir(output), "command": result})
            command = [str(backend / "compiler")]
            if args.cpu is not None:
                command = ["taskset", "-c", str(args.cpu), *command]
            for mode, filename, reference in (("ir", "pystachy.py", "raw.ll"), ("rt", "runtime.py", "seed-rt.ll")):
                output = work / f"witness-{mode}.ll"
                result = runner.execute([*command, mode, str(root / filename), "-o", str(output)], env, args.timeout)
                result["output_sha256"] = sha(output) if output.is_file() else None
                result["matches"] = result["output_sha256"] == inputs[reference]
                report["witnesses"][mode] = result
                atomic_json(destination, report)
                measure.successful(result)
                if not result["matches"]:
                    raise RuntimeError(f"{mode} compiler witness mismatch")
            for sample in range(args.execution_samples):
                output = work / f"execution-{sample}.ll"
                result = runner.execute([*command, "ir", str(root / "pystachy.py"), "-o", str(output)], env, args.timeout)
                result.update(sample=sample, output_sha256=sha(output) if output.is_file() else None)
                result["matches"] = result["output_sha256"] == inputs["raw.ll"]
                report["execution"].append(result)
                atomic_json(destination, report)
                measure.successful(result)
                if not result["matches"]:
                    raise RuntimeError("timed compiler witness mismatch")
            report["source_unchanged"] = source == bootstrap.source_identity(root)
            report["inputs_unchanged"] = inputs == {name: sha(snapshot / name) for name in INPUTS}
            report["tools_unchanged"] = tools == tool_identity(llvm)
            report["harness_unchanged"] = harness == harness_identity()
            values = [r["wall_s"] for r in report["execution"]]
            report["execution_wall_s"] = ({"median": statistics.median(values), "min": min(values), "max": max(values)}
                                          if values else None)
            report["complete"] = all(report[key] for key in
                                     ("source_unchanged", "inputs_unchanged", "tools_unchanged", "harness_unchanged"))
    except BaseException as exc:
        report["error"] = str(exc)
        raise
    finally:
        report["total_wall_s"] = time.monotonic() - started
        report["commands"] = runner.results
        atomic_json(destination, report)
    print(json.dumps({"backend_wall_s": report["backend"]["wall_s"],
                      "backend_cpu_s": report["backend"]["cpu_s"],
                      "backend_peak_rss_kib": report["backend"]["sampled_process_tree_peak_rss_kib"],
                      "execution_wall_s": report["execution_wall_s"], "complete": report["complete"]}, indent=2))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
