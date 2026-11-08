"""Probe intraprocedural LLVM passes on actual Pystachy lowering.

Native agreement and optional llubi cover a finite corpus, not all inputs.
Alive2 is optional; unavailable/incomplete checks never produce a proof status.
"""
import argparse
import ctypes
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys

from ir_cost_report import inventory


ROOT = Path(__file__).resolve().parents[1]
SOURCE = '''def masked_add(a: int, b: int) -> int:
    return (a + b) & 65535


def signed_min(a: int, b: int) -> int:
    if a < b:
        return a
    return b


def affine(a: float, b: float) -> float:
    return a * 1.25 + b
'''
NAMES = ("masked_add", "signed_min", "affine")
FUNCTIONS = {"f." + name for name in NAMES}
WRAPPER = '''#include <stdint.h>
extern int64_t pys_add(int64_t, int64_t) __asm__("f.masked_add");
extern int64_t pys_min(int64_t, int64_t) __asm__("f.signed_min");
extern double pys_affine(double, double) __asm__("f.affine");
int64_t masked_add(int64_t a, int64_t b) { return pys_add(a, b); }
int64_t signed_min(int64_t a, int64_t b) { return pys_min(a, b); }
double affine(double a, double b) { return pys_affine(a, b); }
'''
INTS = (-(1 << 63), -(1 << 63) + 1, -65537, -65536, -1, 0, 1,
        65535, 65536, (1 << 63) - 2, (1 << 63) - 1)
FLOATS = (-math.inf, -1e300, -1.0, -0.0, 0.0, 2.0 ** -1074,
          sys.float_info.min, 1.0, 1.0 + 2.0 ** -52, 1e300, math.inf, math.nan)
SUMMARY = re.compile(
    r"Summary:\s*\n\s*(\d+) correct transformations\s*\n"
    r"\s*(\d+) incorrect transformations\s*\n"
    r"\s*(\d+) failed-to-prove transformations\s*\n\s*(\d+) Alive2 errors\s*$")


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outputs(lookup):
    result = {}
    for name in NAMES:
        values = FLOATS if name == "affine" else INTS
        fn = lookup(name)
        rows = []
        for a, b in itertools.product(values, repeat=2):
            value = fn(a, b)
            # NaN payload/sign are not a Python arithmetic contract. All other
            # doubles, including signed zero and infinities, compare exactly.
            rows.append(("nan" if math.isnan(value) else struct.pack(">d", value).hex())
                        if name == "affine" else str(value))
        result[name] = rows
    return result


def native_outputs(library):
    lib = ctypes.CDLL(str(library))
    for name in NAMES:
        kind = ctypes.c_double if name == "affine" else ctypes.c_int64
        getattr(lib, name).argtypes = [kind, kind]
        getattr(lib, name).restype = kind
    return outputs(lambda name: getattr(lib, name))


def compare(expected, actual):
    if not isinstance(actual, dict) or set(actual) != set(expected):
        raise ValueError("missing or extra kernel results")
    mismatches = []
    for name, wanted in expected.items():
        got = actual[name]
        if not isinstance(got, list) or len(got) != len(wanted):
            raise ValueError(f"wrong result count for {name}")
        mismatches.extend({"function": name, "case": i, "expected": x, "actual": y}
                          for i, (x, y) in enumerate(zip(wanted, got)) if x != y)
    return mismatches


def alive_summary(text, returncode, expected_count):
    # alive-tv may return zero even for incorrect transformations: exit status
    # alone is never sufficient. Reject missing, duplicated or partial summaries.
    matches = list(SUMMARY.finditer(text))
    if (returncode != 0 or expected_count <= 0 or text.count("Summary:") != 1 or len(matches) != 1
            or re.search(r"\b(unsupported|timeout|timed out)\b|^\s*ERROR:", text, re.I | re.M)):
        return {"status": "inconclusive", "refinement_checked": False}
    counts = dict(zip(("correct", "incorrect", "failed_to_prove", "errors"),
                      map(int, matches[0].groups())))
    complete = sum(counts.values()) == expected_count and not (counts["failed_to_prove"] or counts["errors"])
    status = ("verified" if counts["correct"] == expected_count else "counterexample") if complete else "inconclusive"
    return {"status": status, "refinement_checked": status == "verified", **counts}


class RunFailure(Exception):
    pass


class Runner:
    def __init__(self, directory, timeout):
        self.directory = directory
        self.timeout = timeout
        self.steps = []
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("PYSTACHY_") and k not in ("PYTHONPATH", "PYTHONHOME")}
        self.env["PYSTACHY_JOBS"] = "2"
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def run(self, name, argv):
        command = [str(arg) for arg in argv]
        item = {"name": name, "command": command, "status": "error", "returncode": None}
        stdout, stderr = "", ""
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=self.env, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
                item.update(returncode=process.returncode, status="ok" if process.returncode == 0 else "error")
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                item["status"] = "timeout"
        except FileNotFoundError as exc:
            item["status"], stderr = "unavailable", str(exc)
        except OSError as exc:
            stderr = str(exc)
        for kind, data in (("stdout", stdout), ("stderr", stderr)):
            path = self.directory / f"{name}.{kind}.txt"
            path.write_text(data)
            item[kind] = path.name
        self.steps.append(item)
        return item, stdout, stderr

    def require(self, name, argv):
        item, stdout, stderr = self.run(name, argv)
        if item["status"] != "ok":
            raise RunFailure(f"{name}: {item['status']} (see {item['stderr']})")
        return stdout


def tool(name):
    prefix = os.environ.get("PYSTACHY_LLVM")
    return str(Path(prefix) / name) if prefix else (shutil.which(name) or name)


def describe_tool(runner, name, path, absent="unavailable"):
    result = {"path": path, "status": absent}
    if path:
        record, version, _ = runner.run(name + "-version", [path, "--version"])
        resolved = shutil.which(path)
        result.update(status=record["status"], version=version.strip(),
                      executable_sha256=fingerprint(Path(resolved)) if resolved else None)
    return result


def selected_functions(path):
    names = set(inventory(path.read_bytes())["functions"])
    if names != FUNCTIONS:
        raise RunFailure(f"{path.name}: expected {sorted(FUNCTIONS)}, found {sorted(names)}")
    return names


def execute_native(runner, clang, source, label):
    library = runner.directory / (label + ".so")
    runner.require(label + "-build", [clang, "-shared", "-fPIC", "-O0", "-ffp-contract=off",
                                      source, runner.directory / "probe.c", "-o", library])
    text = runner.require(label + "-run", [sys.executable, Path(__file__).resolve(), "--worker", library])
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RunFailure(f"{label}: invalid worker output") from exc


def check_alive(runner, executable, source, target, label):
    selected_functions(source)
    selected_functions(target)
    item, stdout, stderr = runner.run(label, [executable, source, target])
    if item["status"] != "ok":
        return {"status": item["status"], "refinement_checked": False}
    return alive_summary(stdout + stderr, item["returncode"], len(FUNCTIONS))


def interpreter_module(source, expected):
    """Append a bounded driver; each comparison consumes any returned poison."""
    selected_functions(source)
    if (set(expected) != set(NAMES) or any(
            len(expected[name]) != len(FLOATS if name == "affine" else INTS) ** 2 for name in NAMES)):
        raise RunFailure("incomplete interpreter reference corpus")
    lines = [source.read_text(), "define i32 @main(i32 %argc, ptr %argv) {",
             "entry:", "  br label %case0"]
    index = 0
    for name in NAMES:
        values = FLOATS if name == "affine" else INTS
        for row, (a, b) in enumerate(itertools.product(values, repeat=2)):
            floating = name == "affine"
            kind = "double" if floating else "i64"
            args = ["0x" + struct.pack(">d", x).hex().upper() if floating else str(x) for x in (a, b)]
            lines += [f"case{index}:",
                      f"  %r{index} = call {kind} @f.{name}({kind} {args[0]}, {kind} {args[1]})"]
            wanted = expected[name][row]
            if floating and wanted == "nan":
                lines.append(f"  %ok{index} = fcmp uno double %r{index}, %r{index}")
            else:
                value = f"%r{index}"
                if floating:
                    lines.append(f"  %bits{index} = bitcast double {value} to i64")
                    value, wanted = f"%bits{index}", str(int(wanted, 16))
                lines.append(f"  %ok{index} = icmp eq i64 {value}, {wanted}")
            lines.append(f"  br i1 %ok{index}, label %case{index + 1}, label %mismatch")
            index += 1
    lines += [f"case{index}:", "  ret i32 0", "mismatch:", "  ret i32 86", "}"]
    return "\n".join(lines) + "\n"


def poison_rejected(item, stderr):
    return (item["status"] == "error" and item["returncode"] == 1
            and "UB triggered: Branch on poison" in stderr and "Exited with immediate UB." in stderr
            and not re.search(r"unsupported|maximum steps|timeout", stderr, re.I))


def check_interpreter(runner, executable, opt, before, after, wrong, expected):
    result = {"status": "inconclusive", "cases_per_module": sum(map(len, expected.values())),
              "modules_checked": 0, "controls": {}}
    for label, source in (("before", before), ("after", after), ("wrong", wrong)):
        path = runner.directory / ("llubi-" + label + ".ll")
        path.write_text(interpreter_module(source, expected))
        runner.require("verify-llubi-" + label, [opt, "-passes=verify", "-disable-output", path])
        item, stdout, stderr = runner.run("llubi-" + label, [executable, "--max-steps=100000", path])
        if label == "wrong":
            if item["status"] != "error" or item["returncode"] != 86 or stdout.strip() or stderr.strip():
                result["reason"] = "interpreter did not detect the wrong-mask result"
                return result
            result["controls"]["wrong_mask"] = "detected"
        elif item["status"] != "ok" or stdout.strip() or stderr.strip():
            result["reason"] = f"{label}: {item['status']} or unexpected interpreter diagnostics"
            return result
        else:
            result["modules_checked"] += 1
    path = runner.directory / "llubi-poison.ll"
    path.write_text("""define i32 @main(i32 %argc, ptr %argv) {
entry:
  %x = add nsw i8 127, 1
  %c = icmp eq i8 %x, -128
  br i1 %c, label %yes, label %no
yes:
  ret i32 0
no:
  ret i32 0
}
""")
    runner.require("verify-poison", [opt, "-passes=verify", "-disable-output", path])
    item, _, stderr = runner.run("llubi-poison", [executable, "--max-steps=100000", path])
    if poison_rejected(item, stderr):
        result["controls"]["overflow_poison"] = "detected"
        result["status"] = "checked_paths"
    else:
        result["reason"] = "interpreter did not specifically diagnose the overflow-to-poison control"
    return result


def probe(directory, passes="mem2reg,instcombine,simplifycfg", timeout=60, alive_tv=None, require_alive=False, llubi=None):
    if not re.fullmatch(r"[a-z][a-z0-9-]*(?:,[a-z][a-z0-9-]*)*", passes):
        raise ValueError("passes must be a comma-separated list of function pass names")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    runner = Runner(directory, timeout)
    report = {"schema": 1, "status": "incomplete", "refinement_checked": False,
              "scope": "three extracted Pystachy scalar functions; finite native cases",
              "pipeline": f"function({passes})", "python": sys.version,
              "steps": runner.steps, "alive2": {"status": "not_run", "refinement_checked": False},
              "llubi": {"status": "not_run" if llubi else "not_requested"}}
    exit_code = 2
    try:
        if sys.platform != "linux":
            raise RunFailure("native probe currently supports Linux shared libraries only")
        # Record bytes actually compiled, including any local compiler edits.
        sources = [ROOT / "pystachy.py", *sorted((ROOT / "src/pystachy_compiler").glob("*.py"))]
        report["compiler_sources"] = {str(p.relative_to(ROOT)): fingerprint(p) for p in sources}
        report["harness_sha256"] = fingerprint(Path(__file__))
        revision, text, _ = runner.run("git-revision", ["git", "rev-parse", "HEAD"])
        report["revision"] = text.strip() if revision["status"] == "ok" else None
        programs = {name: tool(name) for name in ("opt", "llvm-extract", "clang")}
        report["tools"] = {}
        for name, path in programs.items():
            record = report["tools"][name] = describe_tool(runner, name, path)
            if record["status"] != "ok":
                raise RunFailure(f"{name}: {record['status']} (see {name}-version.stderr.txt)")
        alive = alive_tv or shutil.which("alive-tv")
        report["tools"]["alive-tv"] = describe_tool(runner, "alive", alive)
        report["tools"]["llubi"] = describe_tool(runner, "llubi", llubi, absent="not_requested")
        source = directory / "kernels.py"
        source.write_text(SOURCE)
        (directory / "probe.c").write_text(WRAPPER)
        emitted, before, after, wrong = (directory / name for name in ("emitted.ll", "before.ll", "after.ll", "wrong.ll"))
        runner.require("emit", [sys.executable, ROOT / "pystachy.py", "ir", source, "-o", emitted])
        runner.require("extract", [programs["llvm-extract"], "-S", *["--func=" + name for name in sorted(FUNCTIONS)],
                                   emitted, "-o", before])
        selected_functions(before)
        runner.require("verify-before", [programs["opt"], "-passes=verify", "-disable-output", before])
        runner.require("optimize", [programs["opt"], "-S", "-verify-each", "-passes=" + report["pipeline"], before, "-o", after])
        selected_functions(after)
        runner.require("verify-after", [programs["opt"], "-passes=verify", "-disable-output", after])
        report["llvm_structure"] = "valid"
        reference = {}
        exec(SOURCE, reference)
        expected = outputs(reference.__getitem__)
        (directory / "expected.json").write_text(json.dumps(expected, indent=2) + "\n")
        report["cases"] = {name: len(values) for name, values in expected.items()}
        report["input_values"] = {"int": INTS, "float_hex": [value.hex() for value in FLOATS]}
        report["differential"] = {}
        for label, path in (("before", before), ("after", after)):
            differences = compare(expected, execute_native(runner, programs["clang"], path, label))
            report["differential"][label] = {"status": "mismatch" if differences else "matched", "mismatches": differences}
            if differences:
                raise RunFailure(f"{label}: native results differ from CPython")
        # This control is valid LLVM with intentionally wrong Python semantics.
        original = before.read_text()
        if original.count(", 65535") != 1:
            raise RunFailure("mask negative control no longer matches emitted IR")
        wrong.write_text(original.replace(", 65535", ", 65534"))
        differences = compare(expected, execute_native(runner, programs["clang"], wrong, "wrong"))
        if not differences or any(row["function"] != "masked_add" for row in differences):
            raise RunFailure("native negative control did not detect the changed mask")
        report["controls"] = {"wrong_mask": {"status": "detected", "mismatches": len(differences)}}
        malformed = directory / "malformed.ll"
        malformed.write_text("define i64 @invalid() { ret i32 0 }\n")
        invalid, _, _ = runner.run("malformed", [programs["opt"], "-passes=verify", "-disable-output", malformed])
        if invalid["status"] != "error" or invalid["returncode"] is None or invalid["returncode"] <= 0:
            raise RunFailure("LLVM structural negative control was not rejected")
        report["controls"]["malformed_ir"] = {"status": "detected"}
        report["alive2"] = {"status": report["tools"]["alive-tv"]["status"], "refinement_checked": False}
        report["status"], exit_code = "native_checks_passed", 0
        if alive and report["tools"]["alive-tv"]["status"] == "ok":
            report["alive2"] = check_alive(runner, alive, before, after, "alive-positive")
            report["controls"]["alive_wrong_mask"] = check_alive(runner, alive, before, wrong, "alive-negative")
            if (report["alive2"]["status"] == "verified" and
                    report["controls"]["alive_wrong_mask"]["status"] == "counterexample"):
                report["refinement_checked"] = True
            else:
                report["status"], exit_code = "inconclusive", 2
        elif alive or require_alive:
            report["status"], exit_code = "inconclusive", 2
        if llubi:
            if report["tools"]["llubi"]["status"] == "ok":
                report["llubi"] = check_interpreter(runner, llubi, programs["opt"],
                                                     before, after, wrong, expected)
            else:
                report["llubi"] = {"status": report["tools"]["llubi"]["status"]}
            if report["llubi"]["status"] != "checked_paths":
                report["status"], exit_code = "inconclusive", 2
    except (RunFailure, ValueError) as exc:
        report["status"], report["error"] = "failed", str(exc)
        exit_code = 1
    finally:
        report["artifacts"] = {p.name: fingerprint(p) for p in sorted(directory.iterdir()) if p.is_file()}
        (directory / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report, exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="new directory for raw IR, logs, outputs and report.json")
    parser.add_argument("--passes", default="mem2reg,instcombine,simplifycfg", help="comma-separated intraprocedural passes")
    parser.add_argument("--timeout", type=float, default=60, help="seconds per subprocess")
    parser.add_argument("--alive-tv", help="Alive2 executable, otherwise search PATH")
    parser.add_argument("--require-alive2", action="store_true", help="exit 2 unless refinement and its negative control complete")
    parser.add_argument("--llubi", help="optional UB-aware interpreter; exit 2 if its path checks or controls do not complete")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        print(json.dumps(native_outputs(args.worker), allow_nan=False))
        return 0
    if args.out is None:
        parser.error("--out is required")
    try:
        report, code = probe(args.out, args.passes, args.timeout, args.alive_tv, args.require_alive2, args.llubi)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": report["status"], "refinement_checked": report["refinement_checked"],
                      "alive2": report["alive2"]["status"], "llubi": report["llubi"]["status"],
                      "report": str(args.out.resolve() / "report.json")}))
    return code


if __name__ == "__main__":
    sys.exit(main())
