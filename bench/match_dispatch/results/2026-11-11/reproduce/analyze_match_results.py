#!/usr/bin/env python3
"""Read existing match controller/pyperf reports; never execute a benchmark.

Python standard library only. Input PREFIX names PREFIX-dispatch-measured.json,
PREFIX-pyperf-{if,match}.json, and PREFIX-pyperf-manifest.json. The controller and
manifest must be complete. Without --output-prefix, print Markdown (or --format
json) to stdout. With it, write only PREFIX.json and PREFIX.md analysis files.
"""
import argparse
import hashlib
import json
import math
import shlex
import statistics
import sys
from pathlib import Path

VARIANTS = ("match", "if")
CELL_ORDER = [f"{kind}-{shape}" for kind in ("literal", "tuple", "dataclass")
              for shape in ("mixed", "skewed")]
EXPECTED_CELLS = set(CELL_ORDER)
SOURCE_KEYS = ("bench/match_dispatch/workload.py", "bench/match_dispatch/bench.py",
               "src/pystachy_compiler/patterns.py", "src/pystachy_compiler/expressions.py",
               "src/pystachy_compiler/flow.py", "src/pystachy_compiler/driver.py",
               "pystachy.py", "runtime.py", "runtime.c", "VERSION")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(data), {"path": str(path.resolve()), "bytes": len(data), "sha256": sha(data)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stats(values):
    require(bool(values), "empty measurement series")
    require(all(isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v) and v > 0 for v in values), "nonpositive/nonfinite measurement")
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else None
    return {"n": len(values), "mean": mean, "median": statistics.median(values),
            "sample_stdev": sd, "cv_percent": 100 * sd / mean if sd is not None else None,
            "min": min(values), "max": max(values)}


def dispersion_warnings(label, summary, warnings):
    cv = summary["cv_percent"]
    if cv is not None and cv > 10:
        warnings.append(f"{label}: CV {cv:.3f}% exceeds the analyzer's descriptive 10% flag.")
    if summary["max"] > 1.2 * summary["median"]:
        warnings.append(f"{label}: maximum exceeds the median by more than 20%; inspect the retained observations.")


def validate_record(record, count, checksum, label):
    require(record.get("returncode") == 0, f"{label}: unsuccessful process")
    require(record.get("count") == count and record.get("checksum") == checksum,
            f"{label}: checksum/count mismatch")
    require(record.get("stdout", "").splitlines() == [str(checksum), str(count)],
            f"{label}: unexpected stdout")
    timing = record.get("kernel_wall_ns")
    require(isinstance(timing, int) and not isinstance(timing, bool) and timing > 0,
            f"{label}: invalid kernel timer")
    require(record.get("stderr", "").splitlines() == [f"kernel_wall_ns {timing}"],
            f"{label}: unexpected stderr")


def controller_summary(path):
    report, evidence = load(path)
    require(report.get("status") == "passed", f"{path}: controller is not passed")
    require(report.get("measurement_kind") == "paired_performance", f"{path}: not a timing report")
    settings = report["effective_settings"]
    count = settings["loops"] * settings["size"]
    require(count > 0, f"{path}: invalid dispatch count")
    warnings, rows, names = [], [], set()
    selected_modes = set(report["settings"]["modes"])
    for case in report["cases"]:
        name = case["kind"] + "-" + case["shape"]
        require(name not in names, f"{path}: duplicate cell {name}")
        names.add(name)
        checksum = case["oracle"]["match"]["checksum"]
        for variant in VARIANTS:
            validate_record(case["oracle"][variant], count, checksum, f"{name} CPython oracle {variant}")
        require(set(case["measurements"]) == selected_modes, f"{name}: incomplete execution modes")
        for mode, measurement in case["measurements"].items():
            require(mode in ("cpython", "jit", "aot"), f"unknown execution mode: {mode}")
            pairs = measurement["pairs"]
            require(len(pairs) == settings["samples"], f"{name}/{mode}: missing pairs")
            for number, pair in enumerate(pairs):
                require(sorted(pair.get("order", [])) == sorted(VARIANTS), f"{name}/{mode}: invalid pair order")
                for variant in VARIANTS:
                    validate_record(pair[variant], count, checksum, f"{name}/{mode}/{number}/{variant}")
            row = {"cell": name, "kind": case["kind"], "shape": case["shape"], "mode": mode,
                   "dispatches_per_process": count, "pairs": len(pairs),
                   "kernel_ns": {v: stats([p[v]["kernel_wall_ns"] for p in pairs]) for v in VARIANTS},
                   "command_wall_s": {v: stats([p[v]["wall_s"] for p in pairs]) for v in VARIANTS},
                   "paired_if_over_match": stats([p["if"]["kernel_wall_ns"] / p["match"]["kernel_wall_ns"] for p in pairs])}
            for variant in VARIANTS:
                summary = row["kernel_ns"][variant]
                dispersion_warnings(f"kernel {name}/{mode}/{variant}", summary, warnings)
                if mode != "cpython" and summary["median"] < 10_000_000:
                    warnings.append(f"kernel {name}/{mode}/{variant}: median below 10 ms; short timing samples are sensitive to scheduling noise.")
            rows.append(row)
    require(names == EXPECTED_CELLS, f"{path}: expected all six workload cells, got {sorted(names)}")
    metadata = report["metadata"]
    sources = metadata["source_sha256"]
    source_digest = sha(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode())
    identity = {key: metadata.get(key) for key in ("created_utc", "git_revision", "git_status", "compiler_command",
                "compiler_executable_sha256", "python", "python_executable", "repository_python_version",
                "platform", "cpu_model", "cpu_count", "cpu_affinity", "load_average_start", "environment", "llvm")}
    identity.update(aot_binary_sha256=report.get("aot_binary_sha256"),
                    aot_binary_bytes=report.get("aot_binary_bytes"), artifact_directory=report.get("artifact_directory"),
                    source_files=len(sources), source_manifest_sha256=source_digest,
                    source_manifest_encoding="sha256 of UTF-8 json.dumps(source_sha256, sort_keys=True, separators=(',', ':'))",
                    source_manifest_reference=evidence["path"] + " : metadata.source_sha256",
                    selected_source_sha256={key: sources[key] for key in SOURCE_KEYS if key in sources})
    if metadata.get("git_status"):
        warnings.append("Controller recorded a dirty worktree; use the recorded source hashes, not the commit alone, to identify measured code.")
    return {"settings": settings, "measured_modes": sorted({r["mode"] for r in rows}),
            "rows": rows, "recorded_identity": identity, "evidence": evidence, "warnings": warnings}, report


def pyperf_summary(prefix, controller, raw_controller):
    manifest, manifest_evidence = load(str(prefix) + "-pyperf-manifest.json")
    require(manifest.get("status") == "passed", "pyperf manifest is not passed")
    require(manifest.get("controller_sha256") == controller["evidence"]["sha256"], "pyperf/controller SHA mismatch")
    require(manifest.get("executable_sha256") == controller["recorded_identity"]["aot_binary_sha256"], "pyperf/AOT binary SHA mismatch")
    require(manifest.get("git_revision") == controller["recorded_identity"]["git_revision"], "pyperf/controller revision mismatch")
    loops, size = manifest["workload_loops"], manifest["input_size"]
    settings = controller["settings"]
    require(size == settings["size"] and loops % settings["loops"] == 0, "pyperf workload cannot be checked against controller oracle")
    factor, count = loops // settings["loops"], loops * size
    cases = {c["kind"] + "-" + c["shape"]: c for c in raw_controller["cases"]}
    preflight = set()
    for record in manifest["preflight"]:
        kind, variant, shape, run_loops, run_size = record["command"][-5:]
        name = kind + "-" + shape
        require(name in cases and variant in VARIANTS, "unknown pyperf preflight cell")
        key = (name, variant)
        require(key not in preflight, f"duplicate preflight {key}")
        preflight.add(key)
        require(int(run_loops) == loops and int(run_size) == size, f"{key}: wrong preflight size")
        require(record["count"] == count and record["checksum"] == cases[name]["oracle"][variant]["checksum"] * factor,
                f"{key}: wrong preflight result")
        stats([record["kernel_wall_ns"]])
    require(preflight == {(name, v) for name in cases for v in VARIANTS}, "incomplete pyperf preflight")
    recorded_commands = set()
    for item in manifest["commands"]:
        kind, variant, shape, run_loops, run_size = item["command"][-5:]
        name = kind + "-" + shape
        key = (name, variant, item["worker"])
        require(name in cases and variant == item["variant"] and variant in VARIANTS,
                "invalid pyperf worker command")
        require(key not in recorded_commands and 0 <= item["worker"] < manifest["worker_processes"],
                "duplicate/invalid pyperf worker")
        require(int(run_loops) == loops and int(run_size) == size, "wrong pyperf worker workload size")
        recorded_commands.add(key)
    require(recorded_commands == {(name, variant, worker) for name in cases for variant in VARIANTS
                                   for worker in range(manifest["worker_processes"])},
            "incomplete pyperf worker commands")
    warnings, rows, evidence, suites = [], [], [manifest_evidence], {}
    for variant in VARIANTS:
        suite, item = load(str(prefix) + f"-pyperf-{variant}.json")
        evidence.append(item)
        require(str(suite.get("version")) == "1.0", "unsupported pyperf JSON version")
        suite_meta = suite.get("metadata", {})
        suites[variant] = suite_meta
        require(suite_meta.get("unit") == "second", "expected pyperf seconds")
        require(suite_meta.get("perf_version") == manifest["pyperf_version"], "pyperf version mismatch")
        seen = set()
        for benchmark in suite["benchmarks"]:
            metadata = dict(suite_meta, **benchmark.get("metadata", {}))
            name = metadata["name"]
            require(name in cases and name not in seen, "unknown/duplicate pyperf benchmark name")
            seen.add(name)
            command = shlex.split(metadata["command"])
            kind, run_variant, shape, run_loops, run_size = command[-5:]
            require(name == kind + "-" + shape and run_variant == variant and int(run_loops) == loops and int(run_size) == size,
                    f"{name}/{variant}: command does not describe the measured workload")
            runs = [run for run in benchmark["runs"] if run.get("values")]
            values = [value for run in runs for value in run["values"]]
            require(len(runs) == manifest["worker_processes"], f"{name}/{variant}: unexpected worker count")
            require(all(len(run["values"]) == manifest["values_per_worker"] for run in runs),
                    f"{name}/{variant}: unexpected values per worker")
            for run in runs:
                run_meta = dict(metadata, **run.get("metadata", {}))
                require(run_meta.get("loops") == manifest["pyperf_loops"], f"{name}/{variant}: pyperf loop count mismatch")
            row = {"cell": name, "variant": variant, "command": metadata["command"],
                   "dispatches_per_command": count, "seconds_per_command": stats(values),
                   "measured_worker_runs": len(runs), "excluded_calibration_runs": len(benchmark["runs"]) - len(runs),
                   "excluded_warmup_values": sum(len(run.get("warmups", [])) for run in benchmark["runs"]),
                   "run_summaries": [{"seconds_per_command": stats(run["values"]), "metadata": run.get("metadata", {})} for run in runs]}
            dispersion_warnings(f"pyperf {name}/{variant}", row["seconds_per_command"], warnings)
            rows.append(row)
        require(seen == set(cases), f"pyperf {variant}: incomplete cell coverage")
    by_key = {(r["cell"], r["variant"]): r for r in rows}
    comparisons = []
    for name in cases:
        match = by_key[(name, "match")]["seconds_per_command"]
        manual = by_key[(name, "if")]["seconds_per_command"]
        comparisons.append({"cell": name, "ratio_of_means_if_over_match": manual["mean"] / match["mean"],
                            "ratio_of_medians_if_over_match": manual["median"] / match["median"]})
    identity = {key: value for key, value in manifest.items() if key not in ("commands", "preflight")}
    identity["successful_preflight_cases"] = len(preflight)
    identity["recorded_worker_commands"] = len(manifest["commands"])
    require(len(manifest["commands"]) == len(cases) * len(VARIANTS) * manifest["worker_processes"], "incomplete pyperf worker command manifest")
    return {"rows": rows, "comparisons": comparisons, "recorded_manifest": identity,
            "recorded_suite_metadata": suites, "evidence": evidence, "warnings": warnings}


def dataset(prefix):
    controller, raw = controller_summary(str(prefix) + "-dispatch-measured.json")
    pyperf = pyperf_summary(prefix, controller, raw)
    return {"prefix": str(prefix), "controller": controller, "pyperf": pyperf,
            "warnings": controller.pop("warnings") + pyperf.pop("warnings")}


def compare_datasets(baseline, final):
    before = {(r["cell"], r["mode"]): r for r in baseline["controller"]["rows"]}
    rows = []
    for after in final["controller"]["rows"]:
        key = after["cell"], after["mode"]
        if key not in before or after["mode"] == "cpython":
            continue
        old = before[key]
        rows.append({"cell": key[0], "mode": key[1],
                     "baseline_paired_if_over_match_median": old["paired_if_over_match"]["median"],
                     "final_paired_if_over_match_median": after["paired_if_over_match"]["median"],
                     "baseline_over_final_match_ns_per_dispatch":
                         (old["kernel_ns"]["match"]["median"] / old["dispatches_per_process"])
                         / (after["kernel_ns"]["match"]["median"] / after["dispatches_per_process"]),
                     "baseline_over_final_if_ns_per_dispatch":
                         (old["kernel_ns"]["if"]["median"] / old["dispatches_per_process"])
                         / (after["kernel_ns"]["if"]["median"] / after["dispatches_per_process"])})
    return {"scope": "Descriptive comparison of separate sessions, normalized by dispatch count; not a paired before/after experiment or confidence interval.", "native_kernel_rows": rows}


def pilot_summary(path):
    pilot, evidence = load(path)
    require(pilot.get("status") == "passed", f"{path}: pilot is not complete")
    rows = []
    for case in pilot["cases"]:
        pairs = case["pairs"]
        count = pilot["loops"] * pilot["size"]
        for number, pair in enumerate(pairs):
            checksum = pair["baseline"]["match"]["checksum"]
            for engine in ("baseline", "trial"):
                for variant in VARIANTS:
                    validate_record(pair[engine][variant], count, checksum,
                                    f"pilot {case['kind']}/{case['shape']}/{number}/{engine}/{variant}")
        rows.append({"cell": case["kind"] + "-" + case["shape"], "pairs": len(pairs),
                     "baseline_over_trial_match": stats([p["baseline"]["match"]["kernel_wall_ns"] / p["trial"]["match"]["kernel_wall_ns"] for p in pairs]),
                     "trial_if_over_match": stats([p["trial"]["if"]["kernel_wall_ns"] / p["trial"]["match"]["kernel_wall_ns"] for p in pairs])})
    return {"evidence": evidence, "loops": pilot["loops"], "size": pilot["size"], "rows": rows,
            "scope": "Short diagnostic native-JIT kernel pilot. Baseline compiler native; trial compiler CPython-hosted. Process wall times are not comparable. These results do not replace final native qualification."}


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
                     + ["| " + " | ".join(map(cell, row)) + " |" for row in rows])


def f(value, digits=3):
    return "n/a" if value is None else f"{value:.{digits}f}"


def kernel_table(rows):
    return table(["Cell", "Mode", "Match median ms", "If median ms", "If/match median", "Observed pair span", "Pairs", "CV match / if"],
                 [[r["cell"], r["mode"], f(r["kernel_ns"]["match"]["median"] / 1e6), f(r["kernel_ns"]["if"]["median"] / 1e6),
                   f(r["paired_if_over_match"]["median"]), f(r["paired_if_over_match"]["min"]) + "–" + f(r["paired_if_over_match"]["max"]),
                   r["pairs"], f(r["kernel_ns"]["match"]["cv_percent"], 1) + "% / " + f(r["kernel_ns"]["if"]["cv_percent"], 1) + "%"] for r in rows])


def render_dataset(data, title, compact=False):
    controller, pyperf = data["controller"], data["pyperf"]
    identity = controller["recorded_identity"]
    chunks = ["## " + title, "", "Recorded commit: `" + identity["git_revision"] + "`. Measured modes: " + ", ".join(controller["measured_modes"]) + ".",
              "", "### Kernel timings", "", kernel_table(controller["rows"]), "", "### AOT whole-command pyperf", ""]
    if not compact:
        rows = []
        for row in sorted(pyperf["rows"], key=lambda r: (CELL_ORDER.index(r["cell"]), VARIANTS.index(r["variant"]))):
            s = row["seconds_per_command"]
            rows.append([row["cell"], row["variant"], f(s["mean"], 6), f(s["median"], 6), f(s["sample_stdev"], 6), f(s["cv_percent"], 2) + "%",
                         s["n"], row["measured_worker_runs"], f(s["min"], 6) + "–" + f(s["max"], 6)])
        chunks += [table(["Cell", "Variant", "Mean s", "Median s", "Sample SD s", "CV", "Values", "Workers", "Min–max s"], rows), ""]
    chunks += [table(["Cell", "If/match ratio of means", "If/match ratio of medians"],
                     [[r["cell"], f(r["ratio_of_means_if_over_match"]), f(r["ratio_of_medians_if_over_match"])] for r in pyperf["comparisons"]]), "",
               "### Recorded identities", "", table(["Item", "Recorded value"], [
                   ["Compiler command", json.dumps(identity["compiler_command"])],
                   ["Compiler executable SHA-256", identity["compiler_executable_sha256"]],
                   ["AOT executable SHA-256", identity["aot_binary_sha256"]],
                   ["Source manifest SHA-256", identity["source_manifest_sha256"]],
                   ["Source files", identity["source_files"]],
                   ["Workload source SHA-256", identity["selected_source_sha256"].get("bench/match_dispatch/workload.py", "missing")],
                   ["CPU / affinity", str(identity["cpu_model"]) + " / " + str(identity["cpu_affinity"])],
                   ["CPython", identity["python"]],
                   ["pyperf", pyperf["recorded_manifest"]["pyperf_version"]],
               ]), ""]
    if not compact:
        chunks += [table(["Tool", "Version", "SHA-256"], [[name, detail["version"].splitlines()[0], detail["sha256"]]
                    for name, detail in identity["llvm"].items()]), ""]
    chunks += ["Identities are copied from the measurement records; the analyzer does not inspect current compiler/source files. The full source-hash map remains in the controller report, and its canonical hash is recorded above.", "",
               "### Dispersion and evidence cautions", ""]
    chunks += ["- " + warning for warning in data["warnings"]] if data["warnings"] else ["No CV/long-tail/short-sample flag fired."]
    chunks += ["", "Evidence input hashes:", "", table(["File", "SHA-256"], [[Path(item["path"]).name, item["sha256"]]
                for item in [controller["evidence"]] + pyperf["evidence"]]), ""]
    return chunks


def markdown(report):
    chunks = ["# Match performance evidence", "", report["ratio_direction"], "", report["measurement_scope"], "",
              "All statistics are descriptive. Pair spans and min–max ranges are observed extrema, not confidence intervals. SD is the sample standard deviation (n−1). CV is SD/mean. The 10% CV flag belongs to this analyzer and is not a statistical significance test.", "",
              "Pyperf values are seconds per command invocation as stored by pyperf. Warmups and calibration-only runs are excluded. Values within a worker share a process history, so the total value count is not the number of independent workers. Its mean/median comparisons are ratios of separate summaries, not pairwise value ratios.", ""]
    chunks += render_dataset(report["primary"], "Primary completed measurement")
    if "baseline" in report:
        chunks += render_dataset(report["baseline"], "Preserved initial baseline", compact=True)
        chunks += ["## Baseline versus primary native kernels", "", report["comparison"]["scope"], "",
                   table(["Cell", "Mode", "Baseline if/match", "Primary if/match", "Baseline/primary match per dispatch", "Baseline/primary if per dispatch"],
                         [[r["cell"], r["mode"], f(r["baseline_paired_if_over_match_median"]), f(r["final_paired_if_over_match_median"]),
                           f(r["baseline_over_final_match_ns_per_dispatch"]), f(r["baseline_over_final_if_ns_per_dispatch"])]
                          for r in report["comparison"]["native_kernel_rows"]]), ""]
    for pilot in report.get("pilots", []):
        chunks += ["## Diagnostic pilot: " + Path(pilot["evidence"]["path"]).name, "", pilot["scope"], "",
                   table(["Cell", "Pairs", "Baseline/trial match median", "Observed span", "Trial if/match median"],
                         [[r["cell"], r["pairs"], f(r["baseline_over_trial_match"]["median"]),
                           f(r["baseline_over_trial_match"]["min"]) + "–" + f(r["baseline_over_trial_match"]["max"]),
                           f(r["trial_if_over_match"]["median"])] for r in pilot["rows"]]), ""]
    if report["warnings"]:
        chunks += ["## Cross-report cautions", ""] + ["- " + warning for warning in report["warnings"]] + [""]
    return "\n".join(chunks)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True, help="input path prefix, for example build/match-final")
    parser.add_argument("--baseline-prefix", type=Path)
    parser.add_argument("--pilot", action="append", type=Path, default=[])
    parser.add_argument("--output-prefix", type=Path, help="write PREFIX.json and PREFIX.md; inputs are never modified")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown", help="stdout format when no output prefix")
    args = parser.parse_args(argv)
    report = {"schema_version": 1, "analysis_script_sha256": sha(Path(__file__).read_bytes()),
              "ratio_direction": "If/match ratios above 1 favor match; below 1 favor handwritten conditions.",
              "measurement_scope": "Controller kernel timers exclude input construction, validation, warm-up, compilation and startup. Pyperf command timings include the complete AOT subprocess. Correctness is established by the controller and the manifest's checksum-checked preflight; pyperf command itself discards child stdout/stderr and checks exit status.",
              "primary": dataset(args.prefix), "pilots": [pilot_summary(path) for path in args.pilot], "warnings": []}
    if args.baseline_prefix:
        report["baseline"] = dataset(args.baseline_prefix)
        report["comparison"] = compare_datasets(report["baseline"], report["primary"])
        old = report["baseline"]["controller"]["recorded_identity"]
        new = report["primary"]["controller"]["recorded_identity"]
        for key in ("cpu_model", "cpu_affinity", "llvm"):
            if old[key] != new[key]:
                report["warnings"].append(f"Baseline and primary recorded {key} differ; before/after interpretation is confounded.")
        workload = "bench/match_dispatch/workload.py"
        if old["selected_source_sha256"].get(workload) != new["selected_source_sha256"].get(workload):
            report["warnings"].append("Baseline and primary workload source hashes differ; do not attribute all timing changes to the compiler.")
    text = markdown(report)
    encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output_prefix:
        outputs = [Path(str(args.output_prefix) + extension) for extension in (".json", ".md")]
        inputs = [report["primary"]["controller"]["evidence"]["path"]] + [i["path"] for i in report["primary"]["pyperf"]["evidence"]]
        if "baseline" in report:
            inputs += [report["baseline"]["controller"]["evidence"]["path"]] + [i["path"] for i in report["baseline"]["pyperf"]["evidence"]]
        inputs += [p["evidence"]["path"] for p in report["pilots"]]
        require(not any(str(path.resolve()) in inputs for path in outputs), "output would overwrite an input")
        for path, content in zip(outputs, (encoded, text)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        print("\n".join(str(path.resolve()) for path in outputs))
    else:
        print(encoded if args.format == "json" else text, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, OSError) as error:
        print("analysis error: " + str(error), file=sys.stderr)
        raise SystemExit(2)
