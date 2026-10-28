#!/usr/bin/env python3
"""Fail closed when assembling the parallel CI jobs' verification reports."""
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import dynany_optin
import python_int_gate

ROOT = Path(__file__).resolve().parent.parent
SUITE_STEPS = {"tests-cpython", "tests-native-0", "tests-native-1",
               "tests-opt-off-0", "tests-opt-off-1", "runtime-cache", "python-free-0", "python-free-1",
               "ubsan-0", "ubsan-1", "ubsan-2", "gc-jit-0", "gc-jit-1", "gc-aot-0", "gc-aot-1",
               "gc-aot-2"}
# Steps that run one of the disjoint shards of the corpus (tests/verify.sh shard_cases), and how many
# shards their suite has: the name ends in the shard index.
SHARDED_STEPS = {f"{suite}-{index}": count for suite, count in
                 (("tests-native", 2), ("tests-opt-off", 2), ("python-free", 2),
                  ("ubsan", 3), ("gc-jit", 2), ("gc-aot", 3))
                 for index in range(count)}
GC_STEPS = {"gc-jit-0", "gc-jit-1", "gc-aot-0", "gc-aot-1", "gc-aot-2"}
# The halves of tools/scaling.py's check (tests/verify.sh's SCALING_0 and the shapes it leaves)
SCALING_STEPS = ("scaling-0", "scaling-1")
# The opt-in sweeps' shards (tests/verify.sh's dynany-optin-I and python-int-optin-I groups)
DYNANY_SHARDS = 2
PYTHON_INT_SHARDS = 2
# tests-cpython runs one case in HOSTED_SAMPLE_OF end to end (tests/verify.sh); it compares every
# case's IR, messages and exit status with stage 2's
HOSTED_SAMPLE_OF = 64


def parse_groups(text):
    """Read the harness's public contract, checking that no check is omitted or repeated."""
    groups = {}
    for line in text.splitlines():
        words = line.split()
        if not words:
            continue
        name, *steps = words
        if name in groups:
            raise ValueError(f"duplicate group in --list: {name}")
        if not steps or steps[0] != "bootstrap" or len(set(steps)) != len(steps):
            raise ValueError(f"invalid step list for {name}: bootstrap must come first, once")
        groups[name] = steps
    if not groups or next(iter(groups)) != "all" or len(groups) < 2:
        raise ValueError("--list must begin with all, followed by the CI groups")
    if "bootstrap" in groups and groups["bootstrap"] != ["bootstrap"]:
        raise ValueError("the bootstrap producer must run only bootstrap")
    covered = Counter(step for name, steps in groups.items() if name != "all"
                      for step in steps if step != "bootstrap")
    if covered != Counter(groups["all"][1:]):
        raise ValueError("CI groups must cover every all step exactly once, except bootstrap")
    return groups


def scaling_shapes():
    """The shapes of tools/scaling.py, which scaling-0 and scaling-1 share out."""
    spec = importlib.util.spec_from_file_location("scaling", ROOT / "tools/scaling.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.SHAPES)


def load_groups():
    result = subprocess.run([str(ROOT / "tests/verify.sh"), "--list"], cwd=ROOT,
                            check=True, capture_output=True, text=True, timeout=10)
    return parse_groups(result.stdout)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f"invalid JSON number: {value}")


def number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label}: expected a finite, nonnegative duration")
    return value


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label}: expected an integer >= {minimum}")
    return value


def validate_report(report, group, expected):
    if not isinstance(report, dict) or report.get("project") != "Pystachy":
        raise ValueError(f"{group}: not a Pystachy verification report")
    if report.get("result") != "pass":
        raise ValueError(f"{group}: verification did not pass")
    summary, steps = report.get("summary"), report.get("steps")
    if not isinstance(summary, dict) or not isinstance(steps, list):
        raise ValueError(f"{group}: missing summary or steps")
    names = [step.get("name") if isinstance(step, dict) else None for step in steps]
    if names != expected:
        raise ValueError(f"{group}: step names/order differ: expected {expected}, got {names}")
    for key, value in (("steps", len(expected)), ("passed", len(expected)), ("failed", 0)):
        if integer(summary.get(key), f"{group}.summary.{key}") != value:
            raise ValueError(f"{group}: summary {key} must be {value}")
    number(summary.get("seconds"), f"{group}.summary.seconds")
    for step in steps:
        label = f"{group}.{step['name']}"
        if step.get("result") != "pass":
            raise ValueError(f"{label}: step did not pass")
        number(step.get("seconds"), f"{label}.seconds")
        if "failed" in step and integer(step["failed"], f"{label}.failed") != 0:
            raise ValueError(f"{label}: failed checks")
        if "failures" in step and step["failures"] != []:
            raise ValueError(f"{label}: nonempty failures")
        if step["name"] == "gc-self":
            if (step.get("ir_identical") is not True or
                    integer(step.get("compiler_interval"), f"{label}.compiler_interval", 1) != 5000):
                raise ValueError(f"{label}: missing GC-stressed IR identity or wrong interval")
        if step["name"] == "dynany-fuzz":
            if (integer(step.get("programs"), f"{label}.programs") != 3 or
                    integer(step.get("cases"), f"{label}.cases") != 540 or
                    integer(step.get("parity_cases"), f"{label}.parity_cases") != 90 or
                    step.get("modes") != ["jit", "aot", "jit-gc", "aot-gc"] or
                    integer(step.get("program_gc_interval"), f"{label}.program_gc_interval") != 1 or
                    integer(step.get("mismatches"), f"{label}.mismatches") != 0):
                raise ValueError(f"{label}: expected 3 programs, 540 cases including 90 parity cases, JIT/AOT with program GC stress, and no mismatches")
        if step["name"].startswith("dynany-optin-"):
            optin = step.get("optin")
            dynany_optin.validate_report(optin, root=ROOT)
            if (optin["shard_index"] != int(step["name"].rsplit("-", 1)[1]) or
                    optin["shard_count"] != DYNANY_SHARDS or optin["modes"] != ["jit", "aot"]):
                raise ValueError(f"{label}: wrong dynamic Any shard or modes")
        if step["name"].startswith("python-int-optin-"):
            optin = step.get("python_int_optin")
            python_int_gate.validate_report(optin, root=ROOT)
            if (optin["shard_index"] != int(step["name"].rsplit("-", 1)[1]) or
                    optin["shard_count"] != PYTHON_INT_SHARDS or optin["modes"] != ["jit", "aot"] or
                    optin["gc_stress"] is not False):
                raise ValueError(f"{label}: wrong promoting-int shard, modes or GC setting")
        if step["name"] in GC_STEPS:
            mode = "jit" if step["name"].startswith("gc-jit") else "aot"
            if (step.get("modes") != [mode] or
                    integer(step.get("tests_compiler_interval"), f"{label}.tests_compiler_interval", 1) != 1000 or
                    integer(step.get("tests_interval"), f"{label}.tests_interval", 1) != 1):
                raise ValueError(f"{label}: wrong GC stress mode or intervals")
        if step["name"] == "tests-cpython":
            # Every case compiled alike by both compilers, every syntax case checked alike, and the
            # sample's end-to-end checks (counted below as a suite step's)
            sources = report.get("sources") if isinstance(report.get("sources"), dict) else {}
            if (step.get("ir_identical") is not True or step.get("reference") != "stage2" or
                    integer(step.get("ir_cases"), f"{label}.ir_cases", 1) !=
                    integer(sources.get("corpus_cases"), f"{group}.sources.corpus_cases", 1) or
                    integer(step.get("check_cases"), f"{label}.check_cases", 1) !=
                    integer(sources.get("syntax_cases"), f"{group}.sources.syntax_cases", 1) or
                    step.get("modes") != ["jit", "aot"] or
                    integer(step.get("sample_index"), f"{label}.sample_index") != 0 or
                    integer(step.get("sample_count"), f"{label}.sample_count", 1) != HOSTED_SAMPLE_OF):
                raise ValueError(f"{label}: the CPython-hosted compiler must match stage 2 on every case "
                                 f"and run shard 0 of {HOSTED_SAMPLE_OF} end to end, JIT and AOT")
        if step["name"] in SHARDED_STEPS and (
                integer(step.get("shard_index"), f"{label}.shard_index") != int(step["name"][-1]) or
                integer(step.get("shard_count"), f"{label}.shard_count", 1) != SHARDED_STEPS[step["name"]]):
            raise ValueError(f"{label}: wrong shard")
        if step["name"] in SCALING_STEPS:
            shapes = step.get("shapes")
            if not isinstance(shapes, list) or not shapes or not all(isinstance(x, str) for x in shapes):
                raise ValueError(f"{label}: missing the shapes it checked")
        if step["name"] in SUITE_STEPS:
            expected_checks = integer(step.get("expected"), f"{label}.expected", 1)
            if integer(step.get("passed"), f"{label}.passed") != expected_checks:
                raise ValueError(f"{label}: check coverage differs from expected")
            if integer(step.get("failed"), f"{label}.failed") != 0:
                raise ValueError(f"{label}: failed checks")
    bootstrap = steps[0]
    if bootstrap.get("ir_identical") is not True or not re.fullmatch(
            r"[0-9a-f]{64}", str(bootstrap.get("ir_sha256", ""))):
        raise ValueError(f"{group}: missing successful bootstrap IR identity")
    for key in ("git", "sources", "toolchain"):
        if not isinstance(report.get(key), dict) or not report[key]:
            raise ValueError(f"{group}: missing {key} identity")
    for key in ("suite_checks", "mode_checks"):
        integer(report["sources"].get(key), f"{group}.sources.{key}", 1)
    if not re.fullmatch(r"[0-9a-f]{40}", str(report["git"].get("commit", ""))):
        raise ValueError(f"{group}: invalid git commit")


def merge_reports(directory, groups, expected_commit=None):
    reports, paths = {}, {}
    for path in sorted(directory.rglob("verification.json")):
        report = json.loads(path.read_text(), object_pairs_hook=unique_object,
                            parse_constant=invalid_constant)
        group = report.get("group") if isinstance(report, dict) else None
        if not isinstance(group, str) or group == "all" or group not in groups:
            raise ValueError(f"{path}: unexpected group {group!r}")
        if group in reports:
            raise ValueError(f"duplicate report group: {group}")
        if path != directory / f"verification-{group}" / "verification.json":
            raise ValueError(f"{group}: unexpected report path {path}")
        validate_report(report, group, groups[group])
        reports[group], paths[group] = report, path
    wanted = [name for name in groups if name != "all"]
    if set(reports) != set(wanted):
        raise ValueError(f"missing report groups: {sorted(set(wanted) - set(reports))}")
    shared_bootstrap = "bootstrap" in groups
    if shared_bootstrap:
        # Retain the producer's actual fixed-point proof and duration in the combined report,
        # regardless of the order in --list. Consumers report only their restore/validation work.
        wanted = ["bootstrap", *(name for name in wanted if name != "bootstrap")]
        producer = reports["bootstrap"]["steps"][0]
        bundle_id = producer.get("bootstrap_bundle_id")
        if not isinstance(bundle_id, str) or not re.fullmatch(r"[0-9a-f]{64}", bundle_id):
            raise ValueError("bootstrap: missing or invalid bootstrap bundle identity")
        if producer.get("bootstrap_reused", False) is not False:
            raise ValueError("bootstrap: producer must perform the fixed-point bootstrap")
        for group in wanted[1:]:
            bootstrap = reports[group]["steps"][0]
            if bootstrap.get("bootstrap_bundle_id") != bundle_id:
                raise ValueError(f"{group}: bootstrap bundle identity differs from producer")
            if bootstrap.get("bootstrap_reused") is not True:
                raise ValueError(f"{group}: must validate and reuse the producer's bootstrap")
    # Shards together must make as many checks as an unsharded suite of the same modes (each
    # group's suite is its last step, whose count validate_report checked). The shards of a JIT and
    # AOT suite make as many as tests/verify.sh counts in the whole corpus (sources.suite_checks, the
    # same in every report: see the identities below), opt-off's once per PYSTACHY_OPT setting. The
    # group kind-I runs shard I of its suite step, of as many as SHARDED_STEPS gives that step.
    suite = reports[wanted[0]]["sources"]["suite_checks"]
    for kind, prefix, what in (("native", "tests-native", "native"), ("opt-off", "tests-opt-off", "opt-off"),
                               ("python-free", "python-free", "python-free")):
        count = SHARDED_STEPS[f"{prefix}-0"]
        shards = [reports[f"{kind}-{index}"]["steps"][-1] for index in range(count) if f"{kind}-{index}" in reports]
        if len(shards) < count:
            continue
        runs = 1
        if kind == "opt-off":
            settings = shards[0].get("PYSTACHY_OPT")
            if (not isinstance(settings, list) or not settings or
                    any(shard.get("PYSTACHY_OPT") != settings for shard in shards)):
                raise ValueError("opt-off shards must run the same PYSTACHY_OPT settings")
            runs = len(settings)
        if sum(shard["expected"] for shard in shards) != suite * runs:
            raise ValueError(f"{what} shards must cover the same full-suite check count as the corpus")
    # The shards of a GC suite, which runs in one mode, make as many as the corpus has in one mode
    # (sources.mode_checks), and the UBSan thirds, which run in both modes one at a time, twice as many.
    mode_checks = reports[wanted[0]]["sources"]["mode_checks"]
    for shards, runs, what in ((("gc-jit-0", "gc-jit-1"), 1, "GC JIT"),
                               (("gc-aot-0", "gc-aot-1", "gc-aot-2"), 1, "GC AOT"),
                               (("ubsan-0", "ubsan-1", "ubsan-2"), 2, "UBSan")):
        if (all(group in reports for group in shards) and
                sum(reports[group]["steps"][-1]["expected"] for group in shards) != mode_checks * runs):
            raise ValueError(f"{what} shards must cover the same full-suite check count as the corpus")
    halves = {step["name"]: step["shapes"] for report in reports.values() for step in report["steps"]
              if step["name"] in SCALING_STEPS}
    if len(halves) == len(SCALING_STEPS):
        checked = [shape for name in SCALING_STEPS for shape in halves[name]]
        if sorted(checked) != sorted(scaling_shapes()):
            raise ValueError("scaling-0 and scaling-1 must check every shape of tools/scaling.py, each once")
    int_reports = [step["python_int_optin"] for report in reports.values() for step in report["steps"]
                   if step["name"].startswith("python-int-optin-")]
    if int_reports:
        if len(int_reports) != PYTHON_INT_SHARDS:
            raise ValueError(f"promoting-int compatibility requires all {PYTHON_INT_SHARDS} shards")
        if len({report["compiler_sha256"] for report in int_reports}) != 1:
            raise ValueError("promoting-int compiler identity differs between shards")
        expected_pairs = {(case, mode) for case in python_int_gate.programs(ROOT) for mode in ("jit", "aot")}
        pairs = [(row["case"], row["mode"]) for report in int_reports for row in report["results"]]
        if len(pairs) != len(expected_pairs) or set(pairs) != expected_pairs:
            raise ValueError("promoting-int shards must cover every corpus case and mode exactly once")
    # An opt-in sweep run with --native-suite left the baselines of its exact expected failures and
    # the AOT checks of byte-identical IR ("native-ir") to tests-native: require its full suite,
    # JIT and AOT with the stage-2 compiler, whatever shards it runs in.
    deferring = [step["name"] for report in reports.values() for step in report["steps"]
                 if (step["name"].startswith("dynany-optin-") and step["optin"]["native_suite"]) or
                 (step["name"].startswith("python-int-optin-") and step["python_int_optin"]["native_suite"])]
    if deferring:
        native = [step for report in reports.values() for step in report["steps"]
                  if step["name"].startswith("tests-native")]
        if (not native or sum(step["expected"] for step in native) != suite or
                any(step.get("compiler") != "stage2" or step.get("modes") != ["jit", "aot"] or
                    step.get("passed") != step["expected"] or step.get("failed") != 0 for step in native)):
            raise ValueError(f"{deferring[0]}: defers to tests-native, whose complete stage-2 JIT and AOT suite is missing")
    first = reports[wanted[0]]
    commit = first["git"]["commit"]
    if expected_commit is not None and commit != expected_commit:
        raise ValueError(f"report commit {commit} differs from checkout {expected_commit}")
    identity = {"git.commit": commit, "sources": first["sources"], "toolchain": first["toolchain"]}
    steps, timings = {}, []
    for group in wanted:
        report = reports[group]
        current = {"git.commit": report["git"]["commit"], "sources": report["sources"],
                   "toolchain": report["toolchain"]}
        for key, value in identity.items():
            if json.dumps(current[key], sort_keys=True) != json.dumps(value, sort_keys=True):
                raise ValueError(f"{group}: {key} identity differs between groups")
        if report["steps"][0]["ir_sha256"] != first["steps"][0]["ir_sha256"]:
            raise ValueError(f"{group}: bootstrap IR hash differs between groups")
        for step in report["steps"]:
            if step["name"] in steps:
                continue  # Only bootstrap is repeated: the --list contract checked this.
            step = copy.deepcopy(step)
            step["ci_group"] = group
            if isinstance(step.get("log"), str) and step["log"].startswith("build/"):
                step["log"] = str(paths[group].parent / step["log"][len("build/"):])
            steps[step["name"]] = step
        timings.append({"group": group, "seconds": report["summary"]["seconds"],
                        "steps": report["summary"]["steps"], "report": str(paths[group]),
                        "platform": report.get("platform", {})})
    result = copy.deepcopy(first)
    result["group"] = "all"
    result["steps"] = [steps[name] for name in groups["all"]]
    maximum = round(max(timing["seconds"] for timing in timings), 3)
    critical_path = maximum
    if shared_bootstrap:
        critical_path = round(reports["bootstrap"]["summary"]["seconds"] +
                              max((timing["seconds"] for timing in timings if timing["group"] != "bootstrap"),
                                  default=0), 3)
    result["summary"] = {"steps": len(result["steps"]), "passed": len(result["steps"]),
                         "failed": 0, "seconds": critical_path}
    result["timestamp_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result["ci"] = {"groups": timings, "max_group_seconds": maximum,
                    "critical_path_seconds": critical_path,
                    "runner_seconds": round(sum(timing["seconds"] for timing in timings), 3),
                    "timing_scope": ("verification only; bootstrap then parallel groups; " if shared_bootstrap
                                     else "verification only; parallel groups; ") +
                                    "excludes queue, setup and artifact transfer"}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="downloaded verification artifacts")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        groups = load_groups()
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                                capture_output=True, text=True, timeout=10).stdout.strip()
        result = merge_reports(args.directory, groups, commit)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result = {"project": "Pystachy", "group": "all", "result": "fail", "error": str(exc),
                  "summary": {"steps": 0, "passed": 0, "failed": 1, "seconds": 0}, "steps": []}
        print(f"verification merge: {exc}", file=sys.stderr)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    if result["result"] != "pass":
        return 1
    print(f"verification: {len(result['steps'])} checks passed across {len(result['ci']['groups'])} groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
