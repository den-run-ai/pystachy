"""Compare original/adapted microgpt on CPython and Pystachy JIT/AOT.

Supply the existing upstream names dataset with --input; this tool never
downloads. Every tier receives the same measurement-only source injections.
Short runs retain the original 1000-step learning-rate schedule. Numerical
snapshots and progress output are excluded from in-process timings. Process
wall time includes startup, source loading/JIT and snapshot output.
"""

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import signal
import statistics
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "bench" / "microgpt"
UPSTREAM_COMMIT = "14fb038816c7aae0bb9342c2dbf1a51dd134a5ff"
UPSTREAM_SHA256 = "d47d88c2fd432c8ebdc1048beab7f7eb64ea7e0e664e11b812d72a6d95ebccee"
PREFIX = "MICROGPT_"


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"expected exactly one instrumentation marker: {old!r}")
    return source.replace(old, new)


def replace_line_once(source, pattern, new):
    if len(re.findall(pattern, source, re.MULTILINE)) != 1:
        raise ValueError(f"expected exactly one instrumentation line: {pattern!r}")
    return re.sub(pattern, lambda _: new, source, flags=re.MULTILINE)


def instrument(source):
    """Preserve model/math/RNG; add the same timers and snapshots to both sources."""
    source = replace_once(
        source, "import os       # os.path.exists",
        "import sys\nimport time\n"
        "_bench_steps = int(sys.argv[1])\n"
        "_bench_samples = int(sys.argv[2])\n"
        "_bench_all_gradients = int(sys.argv[3])\n"
        "import os       # os.path.exists",
    )
    source = replace_once(source, "random.seed(42)", "_bench_initialization_start = time.perf_counter()\nrandom.seed(42)")
    source = replace_line_once(
        source, r"^for step in range\([^)]+\):$",
        "_bench_initialization_seconds = time.perf_counter() - _bench_initialization_start\n"
        'print("MICROGPT_INIT", _bench_initialization_seconds)\n'
        'print("MICROGPT_META", [n_layer, n_embd, block_size, n_head, vocab_size, len(params), len(docs), num_steps])\n'
        'print("MICROGPT_INITIAL", [p.data for p in params])\n'
        'print("MICROGPT_DOCS", docs[:_bench_steps])\n'
        'print("MICROGPT_VOCAB", uchars)\n'
        "for step in range(_bench_steps):\n"
        "    _bench_forward_start = time.perf_counter()",
    )
    source = replace_once(
        source, "    loss.backward()",
        "    _bench_forward_seconds = time.perf_counter() - _bench_forward_start\n"
        "    _bench_backward_start = time.perf_counter()\n"
        "    loss.backward()\n"
        "    _bench_backward_seconds = time.perf_counter() - _bench_backward_start\n"
        "    if _bench_all_gradients != 0 or step == 0 or step == _bench_steps - 1:\n"
        '        print("MICROGPT_GRAD", (step, [float(p.grad) for p in params]))\n'
        "    _bench_optimizer_start = time.perf_counter()",
    )
    source = replace_line_once(
        source, r'^    print\(f"step \{step\+1:4d\}.*$',
        "    _bench_optimizer_seconds = time.perf_counter() - _bench_optimizer_start\n"
        '    print("MICROGPT_STEP", (step, n, loss.data, _bench_forward_seconds, _bench_backward_seconds, _bench_optimizer_seconds))',
    )
    source = replace_line_once(
        source, r"^for sample_idx in range\([^)]+\):$",
        "for sample_idx in range(_bench_samples):\n    _bench_sample_start = time.perf_counter()",
    )
    source = replace_line_once(
        source, r'^    print\(f"sample \{sample_idx\+1:2d\}.*$',
        "    _bench_sample_seconds = time.perf_counter() - _bench_sample_start\n"
        '    print("MICROGPT_SAMPLE", (sample_idx, "".join(sample), _bench_sample_seconds))',
    )
    return source.rstrip() + (
        '\nprint("MICROGPT_FINAL", [p.data for p in params])\n'
        'print("MICROGPT_M", m)\nprint("MICROGPT_V", v)\n'
    )


def execute(command, cwd, env, timeout):
    start = time.perf_counter()
    rss_path = None
    measured_command = command
    if sys.platform.startswith("linux") and Path("/usr/bin/time").is_file():
        with tempfile.NamedTemporaryFile(prefix="microgpt-rss-", delete=False) as handle:
            rss_path = Path(handle.name)
        measured_command = ["/usr/bin/time", "-f", "%M", "-o", str(rss_path), *command]
    try:
        with subprocess.Popen(measured_command, cwd=cwd, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=True) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
                timed_out = True
        peak_rss = None
        if rss_path is not None:
            lines = rss_path.read_text().strip().splitlines()
            if lines and lines[-1].isdigit():
                peak_rss = int(lines[-1])
        return {"command": command, "wall_seconds": time.perf_counter() - start,
                "returncode": process.returncode, "timed_out": timed_out,
                "stdout": stdout, "stderr": stderr, "peak_rss_kib": peak_rss}
    except OSError as exc:
        return {"command": command, "wall_seconds": time.perf_counter() - start,
                "returncode": None, "timed_out": False, "stdout": "", "stderr": str(exc), "peak_rss_kib": None}
    finally:
        if rss_path is not None:
            rss_path.unlink(missing_ok=True)


def successful(result):
    return result["returncode"] == 0 and not result["timed_out"]


def compact_result(result):
    return {key: value for key, value in result.items() if key != "stdout"} | {"stdout_tail": result["stdout"][-4000:]}


def finite(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite numerical result")
    elif isinstance(value, (list, tuple)):
        for child in value:
            finite(child)
    elif isinstance(value, dict):
        for child in value.values():
            finite(child)


def parse_output(stdout, steps, samples, all_gradients):
    records = {}
    gradients = {}
    step_values = []
    generated = []
    sample_timings = []
    for line in stdout.splitlines():
        if not line.startswith(PREFIX):
            continue
        tag, literal = line.split(" ", 1)
        value = ast.literal_eval(literal)
        finite(value)
        if tag == "MICROGPT_GRAD":
            index, vector = value
            if str(index) in gradients:
                raise ValueError("duplicate gradient snapshot")
            gradients[str(index)] = vector
        elif tag == "MICROGPT_STEP":
            if len(value) != 6 or value[0] != len(step_values):
                raise ValueError("invalid or out-of-order training step")
            step_values.append(value)
        elif tag == "MICROGPT_SAMPLE":
            index, name, elapsed = value
            if index != len(generated):
                raise ValueError("out-of-order generated sample")
            generated.append(name)
            sample_timings.append(elapsed)
        else:
            if tag in records:
                raise ValueError(f"duplicate record: {tag}")
            records[tag] = value
    required = {"MICROGPT_INIT", "MICROGPT_META", "MICROGPT_INITIAL", "MICROGPT_DOCS",
                "MICROGPT_VOCAB", "MICROGPT_FINAL", "MICROGPT_M", "MICROGPT_V"}
    if set(records) != required or len(step_values) != steps or len(generated) != samples:
        raise ValueError("missing or unexpected result records")
    expected_gradients = {str(i) for i in range(steps)} if all_gradients else {"0", str(steps - 1)}
    if set(gradients) != expected_gradients:
        raise ValueError("gradient checkpoints differ from requested steps")
    metadata = records["MICROGPT_META"]
    if len(metadata) != 8 or metadata[-1] != 1000:
        raise ValueError("model metadata or original learning-rate schedule differs")
    count = metadata[5]
    arrays = [records[key] for key in ("MICROGPT_INITIAL", "MICROGPT_FINAL", "MICROGPT_M", "MICROGPT_V")]
    if any(len(vector) != count for vector in arrays + list(gradients.values())):
        raise ValueError("parameter/gradient/optimizer vector length differs")
    timings = [records["MICROGPT_INIT"], *sample_timings,
               *(elapsed for row in step_values for elapsed in row[3:])]
    if any(elapsed < 0.0 for elapsed in timings):
        raise ValueError("negative timing")
    checks = {
        "metadata": metadata, "docs": records["MICROGPT_DOCS"], "vocabulary": records["MICROGPT_VOCAB"],
        "initial_parameters": records["MICROGPT_INITIAL"], "losses": [row[2] for row in step_values],
        "tokens": [row[1] for row in step_values], "gradients": gradients,
        "final_parameters": records["MICROGPT_FINAL"], "adam_m": records["MICROGPT_M"], "adam_v": records["MICROGPT_V"],
        "generated": generated,
    }
    forward = sum(row[3] for row in step_values)
    backward = sum(row[4] for row in step_values)
    optimizer = sum(row[5] for row in step_values)
    return checks, {
        "initialization_seconds": records["MICROGPT_INIT"],
        "forward_seconds": forward, "backward_seconds": backward, "optimizer_seconds": optimizer,
        "train_seconds": forward + backward + optimizer,
        "inference_seconds": sum(sample_timings),
        "training_tokens": sum(checks["tokens"]),
        "inference_tokens": sum(min(len(name) + 1, metadata[2]) for name in generated),
        "per_step_forward_backward_optimizer_seconds": [row[3:] for row in step_values],
        "per_sample_seconds": sample_timings,
    }


def compare(actual, expected, rtol=1e-9, atol=1e-10):
    summary = {"numeric_values": 0, "max_abs_error": 0.0, "max_relative_error_floor_atol": 0.0,
               "max_scaled_error": 0.0, "rtol": rtol, "atol": atol}

    def walk(a, b, path):
        if isinstance(b, dict):
            if not isinstance(a, dict) or a.keys() != b.keys():
                raise ValueError(f"{path}: dictionary keys differ")
            for key in b:
                walk(a[key], b[key], f"{path}.{key}")
        elif isinstance(b, (list, tuple)):
            if not isinstance(a, (list, tuple)) or len(a) != len(b):
                raise ValueError(f"{path}: sequence lengths differ")
            for index, (av, bv) in enumerate(zip(a, b)):
                walk(av, bv, f"{path}[{index}]")
        elif isinstance(b, float):
            if isinstance(a, bool) or not isinstance(a, (float, int)) or not math.isfinite(a):
                raise ValueError(f"{path}: expected a finite number")
            error = abs(a - b)
            summary["numeric_values"] += 1
            summary["max_abs_error"] = max(summary["max_abs_error"], error)
            summary["max_relative_error_floor_atol"] = max(
                summary["max_relative_error_floor_atol"], error / max(abs(a), abs(b), atol),
            )
            summary["max_scaled_error"] = max(summary["max_scaled_error"], error / (atol + rtol * abs(b)))
            if not math.isclose(a, b, rel_tol=rtol, abs_tol=atol):
                raise ValueError(f"{path}: {a!r} differs from {b!r}")
        elif a != b or type(a) is not type(b):
            raise ValueError(f"{path}: {a!r} differs from {b!r}")

    walk(actual, expected, "checks")
    return summary


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def save(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def normalize_compiler(text):
    parts = shlex.split(text)
    if not parts:
        raise ValueError("compiler command is empty")
    return [str((ROOT / part).resolve()) if not part.startswith("-") and (ROOT / part).is_file() else part for part in parts]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="existing text dataset; its hash is recorded")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--compiler", default=f"{shlex.quote(sys.executable)} pystachy.py")
    parser.add_argument("--python", default=sys.executable, help="CPython interpreter for both baselines")
    parser.add_argument("--all-gradients", action="store_true", help="record every gradient vector; default first/last")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.steps <= 1000 or args.samples < 0 or args.repeats < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("steps must be 1..1000, samples nonnegative, repeats/timeout positive")
    if not args.input.is_file():
        parser.error("--input must be an existing dataset; no downloads are performed")
    original = BENCH / "upstream" / "microgpt.py"
    adapted = BENCH / "microgpt.py"
    raw_original, raw_adapted = original.read_bytes(), adapted.read_bytes()
    if hashlib.sha256(raw_original).hexdigest() != UPSTREAM_SHA256:
        parser.error("vendored upstream source differs from pinned microgpt.py")
    original_source = instrument(raw_original.decode())
    adapted_source = instrument(raw_adapted.decode())
    compiler = normalize_compiler(args.compiler)
    env = os.environ.copy()
    report = {
        "workload": "microgpt scalar autograd training and autoregressive inference; original and adapted source",
        "upstream_commit": UPSTREAM_COMMIT, "original_source_sha256": UPSTREAM_SHA256,
        "adapted_source_sha256": hashlib.sha256(raw_adapted).hexdigest(),
        "original_instrumented_sha256": hashlib.sha256(original_source.encode()).hexdigest(),
        "adapted_instrumented_sha256": hashlib.sha256(adapted_source.encode()).hexdigest(),
        "dataset_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "controller_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "platform": platform.platform(), "controller_python": sys.version,
        "compiler": compiler, "python": args.python,
        "steps": args.steps, "lr_schedule_steps": 1000, "samples": args.samples, "repeats": args.repeats,
        "seed": 42, "all_gradients": args.all_gradients,
        "timing_scope": "timed initialization/forward/backward/Adam/inference; snapshots and progress output excluded; separate process wall and AOT build",
        "environment": {name: env.get(name) for name in (
            "PYSTACHY_OPT", "PYSTACHY_JIT_CODEGEN", "PYSTACHY_JIT_INLINE", "PYSTACHY_CFLAGS",
            "PYSTACHY_GC", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM", "PYSTACHY_LLVM", "PYTHONHASHSEED",
        )},
        "runs": {}, "errors": [],
    }
    report["python_version"] = compact_result(execute([args.python, "--version"], ROOT, env, args.timeout))
    report["compiler_version"] = compact_result(execute(compiler + ["--version"], ROOT, env, args.timeout))
    compiler_files = [Path(part) for part in compiler if Path(part).is_file()]
    report["compiler_file_sha256"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in compiler_files}
    git_cwd = compiler_files[-1].parent if compiler_files else ROOT
    top = execute(["git", "rev-parse", "--show-toplevel"], git_cwd, env, args.timeout)
    if successful(top):
        repository = top["stdout"].strip()
        revision = execute(["git", "rev-parse", "HEAD"], repository, env, args.timeout)
        status = execute(["git", "status", "--short", "--", "pystachy.py", "runtime.py", "runtime.c", "src", "lib", "pyembed.c", "pyext.c"], repository, env, args.timeout)
        report["compiler_git_revision"] = revision["stdout"].strip()
        report["compiler_git_status"] = status["stdout"].strip()
        root = Path(repository)
        paths = [root / name for name in ("pystachy.py", "runtime.py", "runtime.c", "pyembed.c", "pyext.c")]
        paths += list((root / "src").rglob("*.py")) + list((root / "lib").rglob("*.py"))
        report["compiler_source_hashes"] = {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()
        }
    save(report, args.json)
    baseline = None
    with tempfile.TemporaryDirectory(prefix="pystachy-microgpt-") as directory:
        work = Path(directory)
        (work / "input.txt").symlink_to(args.input.resolve())
        original_program = work / "original.py"
        adapted_program = work / "adapted.py"
        original_program.write_text(original_source)
        adapted_program.write_text(adapted_source)
        executable = work / "microgpt"
        build = execute(compiler + ["build", str(adapted_program), "-o", str(executable)], ROOT, env, args.timeout)
        report["aot_build"] = compact_result(build)
        arguments = [str(args.steps), str(args.samples), "1" if args.all_gradients else "0"]
        commands = {
            "original_cpython": [args.python, str(original_program)],
            "adapted_cpython": [args.python, str(adapted_program)],
            "pystachy_jit": compiler + ["run", str(adapted_program)],
        }
        if successful(build):
            commands["pystachy_aot"] = [str(executable)]
            report["aot_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
        else:
            report["errors"].append("AOT build failed; see aot_build")
        save(report, args.json)
        names = list(commands)
        for repetition in range(args.repeats):
            order = names[repetition % len(names):] + names[:repetition % len(names)]
            for name in order:
                result = execute(commands[name] + arguments, work, env, args.timeout)
                record = {"repetition": repetition, "command": result["command"],
                          "wall_seconds": result["wall_seconds"], "returncode": result["returncode"],
                          "timed_out": result["timed_out"], "stderr": result["stderr"],
                          "peak_rss_kib": result["peak_rss_kib"]}
                if not successful(result):
                    record["stdout_tail"] = result["stdout"][-4000:]
                    report["errors"].append(f"{name} repetition{repetition}: execution failed")
                else:
                    try:
                        checks, timing = parse_output(result["stdout"], args.steps, args.samples, args.all_gradients)
                        record["timing"] = timing
                        record["checks_sha256"] = digest(checks)
                        record["loss_first"] = checks["losses"][0]
                        record["loss_last"] = checks["losses"][-1]
                        record["generated"] = checks["generated"]
                        if name == "original_cpython" and baseline is None:
                            baseline = checks
                            report["reference_checks"] = checks
                        if baseline is None:
                            raise ValueError("original CPython reference did not complete")
                        record["comparison"] = compare(checks, baseline)
                    except (ValueError, SyntaxError, TypeError, KeyError) as exc:
                        record["validation_error"] = str(exc)
                        record["stdout_tail"] = result["stdout"][-4000:]
                        report["errors"].append(f"{name} repetition{repetition}: {exc}")
                report["runs"].setdefault(name, []).append(record)
                save(report, args.json)
                train = record.get("timing", {}).get("train_seconds")
                state = "verified" if "comparison" in record else "FAILED"
                print(f"{name} repetition{repetition + 1}: {state}; train={train}; wall={result['wall_seconds']:.3f}s", flush=True)
    report["medians"] = {}
    for name, runs in report["runs"].items():
        verified = [run for run in runs if "comparison" in run]
        if verified:
            report["medians"][name] = {"verified_processes": len(verified),
                "wall_seconds": statistics.median(run["wall_seconds"] for run in verified)}
            rss_values = [run["peak_rss_kib"] for run in verified if run["peak_rss_kib"] is not None]
            if rss_values:
                report["medians"][name]["peak_rss_kib"] = statistics.median(rss_values)
            for key in ("initialization_seconds", "forward_seconds", "backward_seconds", "optimizer_seconds", "train_seconds", "inference_seconds"):
                report["medians"][name][key] = statistics.median(run["timing"][key] for run in verified)
    report["all_verified"] = not report["errors"] and len(report["runs"]) == 4
    save(report, args.json)
    print(f"Results: {args.json}")
    if not report["all_verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
