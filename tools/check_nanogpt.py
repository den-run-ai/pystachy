"""Offline nanoGPT export, elementwise parity checks, and CPU timings.

PyTorch is used only by the reference/export subprocess. The generated native
program reads a plain-text weight file and uses the repository's ndarray port.
No checkpoint, model source, or dependency is downloaded by this tool.
"""

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shlex
import signal
import statistics
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "3adf61e154c3fe3fca428ad6bc3818b27a3b8291"
UPSTREAM_SHA256 = "7c01703240dbec5d554527dc666e35b3df8391d0b117fddc07afcf325a21d11c"
PREFIX = "NANOGPT_"
THREAD_ENV = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
CASES = [
    {"name": "one_token", "n_layer": 1, "n_head": 1, "n_embd": 8,
     "block_size": 5, "vocab_size": 13, "bias": True, "batch": 1, "length": 1},
    {"name": "batched_bias", "n_layer": 2, "n_head": 2, "n_embd": 12,
     "block_size": 5, "vocab_size": 19, "bias": True, "batch": 2, "length": 5},
    {"name": "batched_no_bias", "n_layer": 2, "n_head": 3, "n_embd": 12,
     "block_size": 5, "vocab_size": 17, "bias": False, "batch": 2, "length": 3},
]
BENCHMARK = {"name": "benchmark", "n_layer": 2, "n_head": 2, "n_embd": 64,
             "block_size": 64, "vocab_size": 64, "bias": True, "batch": 2, "length": 16}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute(command, env, timeout, cwd=ROOT):
    start = time.perf_counter()
    try:
        with subprocess.Popen(command, cwd=cwd, env=env, text=True,
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
        result = {"command": command, "returncode": process.returncode,
                  "timed_out": timed_out, "stdout": stdout, "stderr": stderr}
    except OSError as error:
        result = {"command": command, "returncode": None, "timed_out": False,
                  "stdout": "", "stderr": str(error)}
    result["wall_seconds"] = time.perf_counter() - start
    return result


def require_success(result):
    if result["returncode"] != 0 or result["timed_out"]:
        raise ValueError(f"process failed: {result['command']!r}\n{result['stderr'][-4000:]}")


def process_record(result):
    return {key: value for key, value in result.items() if key != "stdout"}


def compare(expected, actual, rtol=1e-9, atol=1e-10):
    """Compare every element, including dict keys, list order and array shapes."""
    count = 0
    max_abs = 0.0
    max_scaled = 0.0

    def visit(want, got, path):
        nonlocal count, max_abs, max_scaled
        if isinstance(want, float):
            if isinstance(got, bool) or not isinstance(got, (float, int)):
                raise ValueError(f"{path}: expected a number")
            if not math.isfinite(want) or not math.isfinite(got):
                raise ValueError(f"{path}: nonfinite value")
            error = abs(want - got)
            allowed = atol + rtol * abs(want)
            count += 1
            max_abs = max(max_abs, error)
            max_scaled = max(max_scaled, error / allowed)
            if error > allowed:
                raise ValueError(f"{path}: {got!r} != {want!r}; absolute error {error}")
        elif isinstance(want, dict):
            if not isinstance(got, dict) or want.keys() != got.keys():
                raise ValueError(f"{path}: dictionary keys differ")
            for key in want:
                visit(want[key], got[key], f"{path}.{key}")
        elif isinstance(want, list):
            if not isinstance(got, list) or len(want) != len(got):
                raise ValueError(f"{path}: list length/type differs")
            for index, (a, b) in enumerate(zip(want, got)):
                visit(a, b, f"{path}[{index}]")
        elif type(want) is not type(got) or want != got:
            raise ValueError(f"{path}: {got!r} != {want!r}")

    visit(expected, actual, "result")
    return {"numeric_values": count, "max_absolute_error": max_abs,
            "max_tolerance_fraction": max_scaled, "rtol": rtol, "atol": atol}


def parse_output(stdout, repeats):
    checks = {}
    timings = {}
    for line in stdout.splitlines():
        if not line.startswith(PREFIX):
            continue
        tag, payload = line.split(" ", 1)
        value = ast.literal_eval(payload)
        if tag == PREFIX + "EDGE":
            if "edge" in checks:
                raise ValueError("duplicate edge result")
            if len(value) != 1:
                raise ValueError("invalid edge result")
            checks["edge"] = {"all_ignored_loss_is_nan": value[0]}
        elif tag in (PREFIX + "FULL", PREFIX + "LAST"):
            key = tag.removeprefix(PREFIX).lower()
            if key in checks:
                raise ValueError("duplicate result")
            if len(value) != (3 if key == "full" else 2):
                raise ValueError("invalid forward result")
            checks[key] = {"shape": value[0], "logits": value[1]}
            if key == "full":
                checks[key]["loss"] = value[2]
        elif tag in (PREFIX + "FULL_TIME", PREFIX + "LAST_TIME", PREFIX + "LOAD_TIME"):
            key = tag.removeprefix(PREFIX).lower()
            if key in timings:
                raise ValueError("duplicate timing")
            timings[key] = value
        else:
            raise ValueError(f"unexpected result tag {tag}")
    if checks.keys() != {"full", "last", "edge"}:
        raise ValueError("missing full, last-token, or edge results")
    if timings.keys() != {"load_time", "full_time", "last_time"}:
        raise ValueError("missing/unexpected timings")
    for key in ("full_time", "last_time"):
        if not isinstance(timings[key], list) or len(timings[key]) != repeats:
            raise ValueError("missing timing repeats")
    flat_times = [timings["load_time"], *timings["full_time"], *timings["last_time"]]
    if any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 for t in flat_times):
        raise ValueError("invalid timing")
    return checks, timings


def write_weights(model, destination):
    cfg = model.config
    parameters = list(model.named_parameters())
    with Path(destination).open("w") as out:
        out.write("PYSTACHY_NANOGPT_V1\n")
        out.write(f"{cfg.n_layer} {cfg.n_head} {cfg.n_embd} {cfg.block_size} {cfg.vocab_size} {int(cfg.bias)}\n")
        out.write(f"{len(parameters)}\n")
        for name, tensor in parameters:
            shape = list(tensor.shape)
            out.write(f"{name} {len(shape)} " + " ".join(map(str, shape)) + "\n")
            values = tensor.detach().reshape(-1).tolist()
            for start in range(0, len(values), 1024):
                out.write(" ".join(repr(value) for value in values[start:start + 1024]) + "\n")


def export_reference(upstream_path, directory, cases, warmups, repeats):
    """Runs only in the selected torch-python subprocess."""
    if digest(upstream_path) != UPSTREAM_SHA256:
        raise ValueError("upstream model.py does not match the pinned source hash")
    import torch

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    spec = importlib.util.spec_from_file_location("nanogpt_upstream_reference", upstream_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"upstream_commit": UPSTREAM_COMMIT, "upstream_sha256": UPSTREAM_SHA256,
                "torch_version": torch.__version__, "torch_config": torch.__config__.show(), "python": sys.version,
                "torch_num_threads": torch.get_num_threads(), "dtype": "float64",
                "dropout": 0.0, "warmups": warmups, "repeats": repeats,
                "created_unix": time.time(), "cases": []}
    for case_index, case in enumerate(cases):
        torch.manual_seed(1729 + case_index)
        config = module.GPTConfig(**{key: value for key, value in case.items() if key not in ("name", "batch", "length")}, dropout=0.0)
        model = module.GPT(config).double().eval()
        name = case["name"]
        weights_path = directory / f"{name}.weights"
        write_weights(model, weights_path)
        n = case["batch"] * case["length"]
        tokens = [(i * 7 + 3) % case["vocab_size"] for i in range(n)]
        targets = [(i * 11 + 5) % case["vocab_size"] for i in range(n)]
        if n > 1:
            targets[-1] = -1
        inputs = {"batch": case["batch"], "length": case["length"], "tokens": tokens, "targets": targets}
        input_path = directory / f"{name}.input"
        input_path.write_text(f"{case['batch']} {case['length']}\n" + " ".join(map(str, tokens)) + "\n" + " ".join(map(str, targets)) + "\n")
        x = torch.tensor(tokens, dtype=torch.long).reshape(case["batch"], case["length"])
        y = torch.tensor(targets, dtype=torch.long).reshape(case["batch"], case["length"])
        checks = {}
        timings = {"full_time": [], "last_time": []}
        with torch.inference_mode():
            for last in (False, True):
                key = "last" if last else "full"
                logits, loss = model(x, None if last else y)
                checks[key] = {"shape": list(logits.shape), "logits": logits.reshape(-1).tolist()}
                if not last:
                    checks[key]["loss"] = loss.item()
                for iteration in range(warmups + repeats):
                    start = time.perf_counter()
                    model(x, None if last else y)
                    elapsed = time.perf_counter() - start
                    if iteration >= warmups:
                        timings[key + "_time"].append(elapsed)
        ignored = torch.full_like(y, -1)
        _, ignored_loss = model(x, ignored)
        checks["edge"] = {"all_ignored_loss_is_nan": math.isnan(ignored_loss.item())}
        record = {"case": case, "inputs": inputs, "weight_sha256": digest(weights_path),
                  "input_sha256": digest(input_path), "checks": checks, "timings": timings,
                  "parameter_count": sum(p.numel() for p in model.parameters())}
        reference_path = directory / f"{name}.json"
        reference_path.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        manifest["cases"].append({"name": name, "reference_sha256": digest(reference_path)})
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def runner_source(backend):
    imports = "from ndarray import matmul\n" if backend == "scalar" else "from ndarray_blas import matmul\n"
    edge_code = """
ignored = [-1] * len(targets)
logits = forward_with_backend(model, tokens, batch, length, matmul, False)
print("NANOGPT_EDGE", (math.isnan(cross_entropy(logits, ignored)),))
"""
    return """import math
import sys
import time
from model import load_weights, forward_with_backend, cross_entropy
from driver import read_input
""" + imports + """
start = time.perf_counter()
model = load_weights(sys.argv[1])
inputs = read_input(sys.argv[2])
tokens = inputs.tokens
targets = inputs.targets
batch = inputs.batch
length = inputs.length
warmups = int(sys.argv[3])
repeats = int(sys.argv[4])
print("NANOGPT_LOAD_TIME", time.perf_counter() - start)
logits = forward_with_backend(model, tokens, batch, length, matmul, False)
loss = cross_entropy(logits, targets)
print("NANOGPT_FULL", (logits.shape, logits.values(), loss))
times: list[float] = []
for iteration in range(warmups + repeats):
    start = time.perf_counter()
    logits = forward_with_backend(model, tokens, batch, length, matmul, False)
    loss = cross_entropy(logits, targets)
    elapsed = time.perf_counter() - start
    if iteration >= warmups:
        times.append(elapsed)
print("NANOGPT_FULL_TIME", times)
logits = forward_with_backend(model, tokens, batch, length, matmul, True)
print("NANOGPT_LAST", (logits.shape, logits.values()))
times = []
for iteration in range(warmups + repeats):
    start = time.perf_counter()
    logits = forward_with_backend(model, tokens, batch, length, matmul, True)
    elapsed = time.perf_counter() - start
    if iteration >= warmups:
        times.append(elapsed)
print("NANOGPT_LAST_TIME", times)
""" + edge_code


def source_hashes():
    paths = [ROOT / "pystachy.py", ROOT / "runtime.py", ROOT / "runtime.c", Path(__file__)]
    for directory in (ROOT / "src", ROOT / "lib", ROOT / "examples" / "nanogpt", ROOT / "examples" / "ndarray"):
        paths.extend(directory.rglob("*.py"))
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(set(paths)) if path.is_file()}


def blas_overlay(source, library, symbol):
    binding = '@extern("libblas.so.3", "cblas_dgemm")'
    if source.count(binding) != 1:
        raise ValueError("expected exactly one default LP64 BLAS binding")
    if not symbol.isidentifier():
        raise ValueError("BLAS symbol must be a C identifier")
    return source.replace(binding, f"@extern({library!r}, {symbol!r})")


def load_reference(fixtures, entry):
    name = entry["name"]
    reference_path = fixtures / f"{name}.json"
    if digest(reference_path) != entry["reference_sha256"]:
        raise ValueError("reference file hash differs")
    reference = json.loads(reference_path.read_text())
    weights = fixtures / f"{name}.weights"
    inputs = fixtures / f"{name}.input"
    if digest(weights) != reference["weight_sha256"] or digest(inputs) != reference["input_sha256"]:
        raise ValueError("input/weight fixture hash differs")
    return reference, weights, inputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-model", type=Path, help="existing pinned upstream nanoGPT model.py")
    parser.add_argument("--torch-python", default=sys.executable)
    parser.add_argument("--python", default=sys.executable, help="CPython interpreter for the scalar native port")
    parser.add_argument("--compiler", default=f"{shlex.quote(sys.executable)} {shlex.quote(str(ROOT / 'pystachy.py'))}")
    parser.add_argument("--fixtures", type=Path, help="reuse an already exported fixture directory; needs no PyTorch")
    parser.add_argument("--export-only", type=Path, help="export reusable offline fixtures and stop")
    parser.add_argument("--benchmark", action="store_true", help="also run the larger 2-layer, 64-wide benchmark case")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--blas-library", help="optional shared library path/name for native CBLAS")
    parser.add_argument("--blas-symbol", default="cblas_dgemm", help="LP64 CBLAS dgemm symbol (used with --blas-library)")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--reference-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.repeats < 1 or args.warmups < 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("repeats >= 1, warmups >= 0 and finite timeout > 0 are required")
    if args.fixtures and (args.export_only or args.upstream_model):
        parser.error("--fixtures cannot be combined with --upstream-model or --export-only")
    if not args.fixtures and args.upstream_model is None:
        parser.error("supply --upstream-model or --fixtures")
    if not args.export_only and args.json is None:
        parser.error("--json is required unless exporting only")
    cases = CASES + ([BENCHMARK] if args.benchmark else [])
    if args.reference_worker:
        export_reference(args.upstream_model.resolve(), args.export_only.resolve(), cases,
                         args.warmups, args.repeats)
        return 0
    env = dict(os.environ)
    env.update({name: "1" for name in THREAD_ENV})
    env["PYTHONHASHSEED"] = "0"
    paths = [str(ROOT / "examples" / "nanogpt"), str(ROOT / "examples" / "ndarray")]
    env["PYSTACHY_PATH"] = os.pathsep.join(paths)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    revision = execute(["git", "rev-parse", "HEAD"], env, args.timeout)
    status = execute(["git", "status", "--porcelain", "--", "pystachy.py", "runtime.py", "runtime.c", "src", "lib", "examples/nanogpt", "examples/ndarray", "tools/check_nanogpt.py"], env, args.timeout)
    report = {"schema": 1, "platform": platform.platform(), "machine": platform.machine(),
              "controller_python": sys.version, "thread_environment": {k: env[k] for k in THREAD_ENV},
              "runtime_environment": {k: env[k] for k in ("PYSTACHY_LLVM", "PYSTACHY_GC", "PYSTACHY_GC_STRESS_PROGRAM", "PYSTACHY_GC_STRESS_COMPILER") if k in env},
              "git_revision": revision["stdout"].strip(), "git_status": status["stdout"].splitlines(),
              "source_hashes": source_hashes(), "builds": {}, "cases": {}, "errors": [],
              "all_verified": False, "reference_exported_in_this_run": args.fixtures is None}
    def save():
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    with tempfile.TemporaryDirectory(prefix="pystachy-nanogpt-") as temp:
        temp = Path(temp)
        if args.blas_library:
            adapter = ROOT / "examples" / "ndarray" / "ndarray_blas.py"
            source = blas_overlay(adapter.read_text(), args.blas_library, args.blas_symbol)
            (temp / "ndarray_blas.py").write_text(source)
            library = Path(args.blas_library)
            report["blas"] = {"library": args.blas_library, "symbol": args.blas_symbol,
                              "library_sha256": digest(library) if library.is_file() else None,
                              "overlay_sha256": hashlib.sha256(source.encode()).hexdigest(),
                              "integer_abi": "LP64 (32-bit C int)"}
        fixtures = (args.fixtures or args.export_only or (temp / "fixtures")).resolve()
        if not args.fixtures:
            command = [args.torch_python, str(Path(__file__).resolve()), "--reference-worker",
                       "--upstream-model", str(args.upstream_model.resolve()), "--export-only", str(fixtures),
                       "--warmups", str(args.warmups), "--repeats", str(args.repeats)]
            if args.benchmark:
                command.append("--benchmark")
            result = execute(command, env, args.timeout)
            report["export_process"] = process_record(result)
            save()
            require_success(result)
            if args.export_only:
                print(f"Exported offline nanoGPT fixtures to {fixtures}")
                return 0
        manifest = json.loads((fixtures / "manifest.json").read_text())
        if manifest["upstream_sha256"] != UPSTREAM_SHA256:
            raise ValueError("fixture upstream hash differs")
        if any(manifest[key] != getattr(args, key) for key in ("warmups", "repeats")):
            raise ValueError("fixture warmups/repeats differ from requested settings")
        report["reference_manifest"] = manifest
        compiler = shlex.split(args.compiler)
        commands = {}
        for backend in ["scalar"] + (["blas"] if args.blas_library else []):
            source = temp / f"runner_{backend}.py"
            source.write_text(runner_source(backend))
            executable = temp / f"runner_{backend}"
            result = execute([*compiler, "build", str(source), "-o", str(executable)], env, args.timeout)
            report["builds"][backend] = process_record(result) | {"runner_sha256": digest(source)}
            if result["returncode"] == 0 and not result["timed_out"]:
                report["builds"][backend]["binary_sha256"] = digest(executable)
                commands[backend + "_aot"] = [str(executable)]
            else:
                report["errors"].append(f"{backend}: AOT build failed")
            commands[backend + "_jit"] = [*compiler, "run", str(source)]
            if backend == "scalar":
                commands["scalar_cpython"] = [args.python, str(source)]
            save()
        for case_index, entry in enumerate(manifest["cases"]):
            name = entry["name"]
            reference, weights, inputs = load_reference(fixtures, entry)
            record = {"reference": reference, "tiers": {}}
            report["cases"][name] = record
            tiers = list(commands)
            tiers = tiers[case_index % len(tiers):] + tiers[:case_index % len(tiers)]
            for tier in tiers:
                result = execute([*commands[tier], str(weights), str(inputs), str(args.warmups), str(args.repeats)], env, args.timeout)
                row = process_record(result)
                record["tiers"][tier] = row
                try:
                    require_success(result)
                    actual, timings = parse_output(result["stdout"], args.repeats)
                    row["comparison"] = compare(reference["checks"], actual)
                    row["timings"] = timings
                    row["median_full_seconds"] = statistics.median(timings["full_time"])
                    row["median_last_seconds"] = statistics.median(timings["last_time"])
                    row["verified"] = True
                    print(f"{name} {tier}: verified {row['comparison']['numeric_values']} values, full={row['median_full_seconds']:.6f}s last={row['median_last_seconds']:.6f}s", flush=True)
                except (ValueError, SyntaxError, TypeError, KeyError) as error:
                    row["verified"] = False
                    row["error"] = str(error)
                    row["stdout_tail"] = result["stdout"][-2000:]
                    report["errors"].append(f"{name} {tier}: {error}")
                    print(report["errors"][-1], file=sys.stderr, flush=True)
                save()
        report["all_verified"] = not report["errors"] and bool(report["cases"])
        save()
    return 0 if report["all_verified"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        print(f"nanoGPT check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
