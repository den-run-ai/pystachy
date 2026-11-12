"""Time the AskMe port on several Python runtimes with model latency removed.

Every model reply is recorded in advance, so a run measures only the agent
harness: process startup, prompt building, reply decoding, policy decisions
and the file and shell actions. Each runtime first has to reproduce the
CPython transcript (model requests, events, console, result and workspace)
before any of its runs is timed.

usage: bench.py [--out RESULT] [--runs N] [--askme CHECKOUT] [--pypy PYPY]
                [--mypyc MYPYC] [--pystachy PYSTACHY] [--port DIR] [--core N]
                [--verify-only]
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RECORDED_ENDPOINT = "http://127.0.0.1:9/v1/chat/completions"
CONFIG_VARIABLES = (
    "LLM_BACKEND",
    "LLM_API_URL",
    "LLM_MODEL",
    "LLM_CAPABILITY_PROFILE",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENROUTER_PROVIDER",
    "OPENROUTER_ALLOW_FALLBACKS",
    "OPENROUTER_REQUIRE_PARAMETERS",
    "OPENROUTER_REASONING_EFFORT",
    "ALLOW_SYSTEM_INSTALLS",
    "ALLOW_NETWORK",
    "AGENT_COMPILE_REPAIR",
    "AGENT_REASONING_POLICY",
    "AGENT_STEP_POLICY",
    "AGENT_FINAL_VALIDATE",
    "AGENT_GOAL_CONTEXT_CHARS",
    "AGENT_RUN_LOG",
    "ASKME_NATIVE_TIMEOUT_TOOL",
    "PYSTACHY_HOME",
    "PYSTACHY_PATH",
)
STAMP = re.compile(r"^\[\d\d:\d\d:\d\d\] ")
SECONDS = re.compile(r"\b\d+\.\d+s\b")
# The one scenario that waits for a real five-second shell timeout.
SKIPPED_SCENARIOS = ("timeout_retry",)


def environment(scenario, run_log):
    env = {key: value for key, value in os.environ.items() if key not in CONFIG_VARIABLES}
    env.update(
        {
            "LLM_BACKEND": "local",
            "LLM_API_URL": RECORDED_ENDPOINT,
            "LLM_MODEL": "recorded-model",
            "AGENT_RUN_LOG": str(run_log),
            "LC_ALL": "C",
            # Scenario commands must not leave bytecode in the compared
            # workspace. The harness itself is precompiled below.
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    env.update(scenario["env"])
    return env


def normalize(value, workspace):
    if isinstance(value, dict):
        return {
            key: 0
            if key in ("wall_s", "llm_wall_s") and isinstance(item, (int, float))
            else normalize(item, workspace)
            for key, item in value.items()
            if key != "ts"
        }
    if isinstance(value, list):
        return [normalize(item, workspace) for item in value]
    if isinstance(value, str):
        return value.replace(workspace, "<WS>")
    return value


class Run:
    """One process: its measurements and, on request, its transcript digest."""

    def __init__(self, wall, cpu, rss_kb, exit_code, digest, parts):
        self.wall = wall
        self.cpu = cpu
        self.rss_kb = rss_kb
        self.exit_code = exit_code
        self.digest = digest
        self.parts = parts


class Bench:
    def __init__(self, work, core):
        self.work = Path(work)
        self.pin = ["taskset", "-c", str(core)] if shutil.which("taskset") else []
        # A megabyte-sized launcher: a child's peak RSS starts from the image
        # that forked it, which must not be this driver.
        self.timer = str(self.work / "timerun")
        subprocess.run(
            [os.environ.get("CC", "cc"), "-O2", "-o", self.timer, str(HERE / "timerun.c")],
            check=True,
        )
        self.report = self.work / "timerun.txt"
        # One workspace path for every run: outputs that quote an absolute
        # path are cut by length, and `pystachy run` keys its program cache
        # on the working directory.
        self.base = self.work / "run"
        self.workspace = self.base / "ws"

    def prepare(self, scenario):
        shutil.rmtree(self.base, ignore_errors=True)
        self.workspace.mkdir(parents=True)
        for relative, content in scenario["files"].items():
            target = self.workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        (self.base / "replay.json").write_text(json.dumps(scenario["replay"]), encoding="utf-8")

    def run(self, scenario, command, collect=False, extra_env=None, use_replay=True):
        self.prepare(scenario)
        replay = self.base / "replay.json"
        request_log = self.base / "requests.jsonl"
        argv = list(command(replay, request_log) if use_replay else command(None, request_log))
        argv += ["--working-dir", str(self.workspace), "--result-json", "result.json"]
        argv += scenario["args"] + [scenario["prompt"]]
        env = environment(scenario, self.base / "run.jsonl")
        env.update(extra_env or {})
        with open(self.base / "stdout.txt", "wb") as out, open(self.base / "stderr.txt", "wb") as err:
            run = self.launch(argv, self.base, env, out, err)
        if collect:
            parts = self.transcript()
            parts["exit_code"] = run.exit_code
            run.parts = parts
            run.digest = hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()
        return run

    def launch(self, argv, cwd, env, out, err):
        """One process through the launcher: wall, CPU, peak RSS and exit code."""
        subprocess.run(
            self.pin + [self.timer, str(self.report)] + argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            check=True,
        )
        wall, user, system, rss_kb, code = self.report.read_text().split()
        return Run(float(wall), float(user) + float(system), int(rss_kb), int(code), None, None)

    def transcript(self):
        workspace = str(self.workspace)
        console = [
            SECONDS.sub("0.0s", STAMP.sub("", line).replace(workspace, "<WS>"))
            for line in (self.base / "stdout.txt").read_text(encoding="utf-8").splitlines()
        ]

        def jsonl(name):
            path = self.base / name
            if not path.exists():
                return []
            return [
                normalize(json.loads(line), workspace)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]

        result = None
        if (self.base / "result.json").exists():
            result = normalize(json.loads((self.base / "result.json").read_text()), workspace)
        files = {
            str(path.relative_to(self.workspace)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(self.workspace.rglob("*"))
            if path.is_file()
        }
        return {
            "console": console,
            "events": jsonl("run.jsonl"),
            "requests": jsonl("requests.jsonl"),
            "result": result,
            "workspace": files,
        }


def port_command(prefix):
    def command(replay, request_log):
        argv = list(prefix)
        if replay is not None:
            argv += ["--replay", str(replay)]
        return argv + ["--request-log", str(request_log)]

    return command


REFERENCE_FILES = (
    "askme.py",
    "actions.py",
    "llm.py",
    "loop.py",
    "policies.py",
    "state.py",
    "tests/native_replay_upstream.py",
)


def copy_reference(askme, target):
    """A private copy of the reference harness: its bytecode caches stay here."""
    for name in REFERENCE_FILES:
        (target / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(Path(askme) / name, target / name)
    return target


def reference_command(python, reference):
    driver = str(reference / "tests" / "native_replay_upstream.py")

    def command(replay, request_log):
        if replay is None:
            # Live HTTP: the unmodified CLI with its own requests transport.
            return [python, str(reference / "askme.py")]
        return [python, driver, str(replay), str(request_log)]

    return command


class RecordedServer:
    """A loopback chat-completions endpoint that answers from a reply list."""

    def __init__(self):
        outer = self
        self.replies = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                payload = outer.replies.pop(0)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/chat/completions"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def load(self, scenario):
        self.replies = [json.dumps(entry).encode() for entry in scenario["replay"]]

    def close(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()


def first_difference(expected, actual):
    """The first differing item of two transcript parts, for a failure message."""
    if isinstance(expected, list) and isinstance(actual, list):
        for index, (left, right) in enumerate(zip(expected, actual)):
            if left != right:
                return f"  [{index}] cpython: {left!r}\n  [{index}] runtime: {right!r}"[:2000]
        return f"  lengths {len(expected)} and {len(actual)}"
    return f"  cpython: {expected!r}\n  runtime: {actual!r}"[:2000]


def summarize(samples):
    walls = sorted(sample["wall"] for sample in samples)
    return {
        "runs": len(samples),
        "wall_median_ms": round(statistics.median(walls) * 1000, 2),
        "wall_min_ms": round(walls[0] * 1000, 2),
        "wall_max_ms": round(walls[-1] * 1000, 2),
        "cpu_median_ms": round(statistics.median(s["cpu"] for s in samples) * 1000, 2),
        "rss_median_mb": round(statistics.median(s["rss_kb"] for s in samples) / 1024, 1),
    }


def tool_version(argv):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    lines = (done.stdout + done.stderr).strip().splitlines()
    return " ".join(lines[-1].split()) if lines else "unknown"


def git_commit(path):
    done = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True
    )
    return done.stdout.strip() or "unknown"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default="build/askme-runtimes", help="Path of the JSON result")
    parser.add_argument("--runs", type=int, default=15)
    parser.add_argument("--port", default=str(ROOT / "examples" / "askme"))
    parser.add_argument("--askme", help="AskMe checkout with the reference harness")
    parser.add_argument("--reference-python", help="Python with requests, for the reference")
    parser.add_argument("--reference-pypy", help="PyPy with requests, for the reference")
    parser.add_argument("--pypy")
    parser.add_argument("--mypyc")
    parser.add_argument("--pystachy", default=str(ROOT / "pystachy"))
    parser.add_argument("--core", type=int, default=2)
    parser.add_argument("--steady", default="20x100", help="TASKSxSTEPS of the long run")
    parser.add_argument(
        "--verify-only", action="store_true", help="Compare transcripts, then stop without timing"
    )
    args = parser.parse_args()

    # Runs start in a scratch directory: name every tool by an absolute path.
    for option in ("pypy", "mypyc", "pystachy", "reference_python", "reference_pypy"):
        value = getattr(args, option)
        if value:
            found = shutil.which(value)
            if found is None:
                raise SystemExit(f"--{option.replace('_', '-')}: {value} is not an executable")
            setattr(args, option, os.path.abspath(found))
    source = Path(args.port).resolve()
    work = Path(tempfile.mkdtemp(prefix="askme_bench_"))
    # Interpreters run a private, precompiled copy: an installed program has
    # its bytecode cache, and the checkout stays clean.
    port = work / "port"
    shutil.copytree(source, port, ignore=shutil.ignore_patterns("__pycache__"))
    main_py = str(port / "askme_native.py")
    bench = Bench(work, args.core)

    def precompile(interpreter, directory):
        subprocess.run([interpreter, "-m", "compileall", "-q", str(directory)], check=True)

    precompile(sys.executable, port)
    if args.pypy:
        precompile(args.pypy, port)
    python = sys.executable
    builds = {}
    runtimes = {"cpython": port_command([python, main_py])}
    if args.pypy:
        runtimes["pypy"] = port_command([args.pypy, main_py])
    if args.mypyc:
        build = work / "mypyc"
        build.mkdir()
        modules = sorted(path.name for path in port.glob("*.py"))
        for name in modules:
            shutil.copy(port / name, build / name)
        started = time.perf_counter()
        subprocess.run(
            [args.mypyc, *modules], cwd=build, check=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        builds["mypyc_build_s"] = round(time.perf_counter() - started, 1)
        compiled = work / "mypyc_run"
        compiled.mkdir()
        size = 0
        for library in build.glob("*.so"):
            shutil.copy(library, compiled / library.name)
            size += library.stat().st_size
        builds["mypyc_extension_bytes"] = size
        (compiled / "run.py").write_text(
            "import sys\nimport askme_native\n"
            "assert askme_native.__file__.endswith('.so')\nsys.exit(askme_native.main())\n"
        )
        mypyc_python = str(Path(args.mypyc).parent / "python")
        runtimes["mypyc"] = port_command([mypyc_python, str(compiled / "run.py")])
    if args.pystachy:
        executable = work / "askme"
        started = time.perf_counter()
        subprocess.run([args.pystachy, "build", main_py, "-o", str(executable)], check=True)
        builds["pystachy_aot_build_s"] = round(time.perf_counter() - started, 1)
        builds["pystachy_aot_bytes"] = executable.stat().st_size
        runtimes["pystachy-jit"] = port_command([args.pystachy, "run", main_py])
        runtimes["pystachy-aot"] = port_command([str(executable)])
    reference = None
    if args.askme:
        reference = copy_reference(args.askme, work / "reference")
        reference_python = args.reference_python or python
        precompile(reference_python, reference)
        runtimes["reference-cpython"] = reference_command(reference_python, reference)
        if args.reference_pypy:
            precompile(args.reference_pypy, reference)
            runtimes["reference-pypy"] = reference_command(args.reference_pypy, reference)

    scenarios = {}
    for path in sorted((source / "scenarios").glob("*.json")):
        if path.stem not in SKIPPED_SCENARIOS:
            scenarios[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    tasks, steps = (int(part) for part in args.steady.split("x"))
    sys.path.insert(0, str(HERE))
    import workload

    steady = workload.build(tasks, steps)
    light = workload.build_light(tasks, steps)
    workloads = dict(scenarios)
    workloads["steady"] = steady
    workloads["light"] = light

    # 1. Correctness before timing: every runtime reproduces CPython's transcript.
    print(f"verifying {len(runtimes)} runtimes on {len(workloads)} workloads", flush=True)
    baseline = {}
    verification = {}
    cold_jit = None
    for name, scenario in workloads.items():
        baseline[name] = bench.run(scenario, runtimes["cpython"], collect=True)
        if baseline[name].exit_code != scenario["exit_code"]:
            raise SystemExit(f"{name}: CPython exit {baseline[name].exit_code}")
    for runtime, command in runtimes.items():
        if runtime == "cpython":
            continue
        for name, scenario in workloads.items():
            run = bench.run(scenario, command, collect=True)
            if runtime == "pystachy-jit" and cold_jit is None:
                cold_jit = run.wall  # the first launch compiles and fills the program cache
            if run.digest != baseline[name].digest:
                for part, value in baseline[name].parts.items():
                    if value != run.parts[part]:
                        raise SystemExit(
                            f"{runtime} differs from cpython on {name}: {part}\n"
                            + first_difference(value, run.parts[part])
                        )
        verification[runtime] = len(workloads)
        print(f"  {runtime}: {len(workloads)} transcripts equal", flush=True)
    for run in baseline.values():
        run.parts = None  # the digests are enough from here on
    if cold_jit is not None:
        builds["pystachy_jit_first_launch_s"] = round(cold_jit, 2)
    if args.verify_only:
        shutil.rmtree(work, ignore_errors=True)
        return 0

    results = {}

    def measure(label, scenario, selected, runs, extra_env=None, use_replay=True, before=None):
        samples = {runtime: [] for runtime in selected}
        for _round in range(runs):
            for runtime in selected:  # interleaved: one shared-host burst hits every runtime
                if before:
                    before()
                run = bench.run(scenario, runtimes[runtime], extra_env=extra_env, use_replay=use_replay)
                if run.exit_code != scenario["exit_code"]:
                    raise SystemExit(f"{label}/{runtime}: exit {run.exit_code}")
                samples[runtime].append({"wall": run.wall, "cpu": run.cpu, "rss_kb": run.rss_kb})
        results[label] = {
            runtime: {"summary": summarize(values), "samples": values}
            for runtime, values in samples.items()
        }
        row = "  ".join(
            f"{runtime}={results[label][runtime]['summary']['wall_median_ms']:.0f}ms"
            for runtime in selected
        )
        print(f"  {label}: {row}", flush=True)

    # 2. Startup floor: --help, no run at all.
    print("timing", flush=True)
    help_scenario = {"prompt": "--help", "args": [], "env": {}, "files": {}, "replay": [], "exit_code": 0}
    help_samples = {runtime: [] for runtime in runtimes}
    bench.prepare(help_scenario)
    for round_number in range(args.runs + 1):
        for runtime, command in runtimes.items():
            if runtime.startswith("reference"):
                argv = [command(None, None)[0], str(reference / "askme.py"), "--help"]
            else:
                argv = [part for part in command(None, "x") if part not in ("--request-log", "x")]
                argv.append("--help")
            env = environment(help_scenario, work / "none.jsonl")
            with open(os.devnull, "wb") as sink:
                run = bench.launch(argv, bench.base, env, sink, sink)
            if run.exit_code != 0:
                raise SystemExit(f"help/{runtime}: exit {run.exit_code}")
            if round_number:  # the first round only warms file and program caches
                help_samples[runtime].append(
                    {"wall": run.wall, "cpu": run.cpu, "rss_kb": run.rss_kb}
                )
    results["help"] = {
        runtime: {"summary": summarize(values), "samples": values}
        for runtime, values in help_samples.items()
    }
    print(
        "  help: "
        + "  ".join(f"{r}={results['help'][r]['summary']['wall_median_ms']:.0f}ms" for r in runtimes),
        flush=True,
    )

    # 3. Whole runs with recorded replies.
    everyone = list(runtimes)
    for name, scenario in scenarios.items():
        measure(name, scenario, everyone, args.runs)
    long_runs = max(5, args.runs // 3)
    measure("steady", steady, everyone, long_runs)
    measure("light", light, everyone, long_runs)

    # 4. The real transports against an instant loopback server.
    if shutil.which("curl"):
        server = RecordedServer()
        http_env = {"LLM_API_URL": server.url}
        http_scenario = workload.build(2, 51)
        selected = [r for r in runtimes if r != "reference-pypy"]
        measure(
            "http",
            http_scenario,
            selected,
            long_runs,
            extra_env=http_env,
            use_replay=False,
            before=lambda: server.load(http_scenario),
        )
        results["http"]["requests"] = len(http_scenario["replay"])
        server.close()

    suite = {}
    for runtime in runtimes:
        suite[runtime] = round(
            sum(results[name][runtime]["summary"]["wall_median_ms"] for name in scenarios), 1
        )
    report = {
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "machine": {
            "cpu": platform.processor() or platform.machine(),
            "cpu_model": _cpu_model(),
            "cores": os.cpu_count(),
            "kernel": platform.release(),
            "pinned_core": args.core if bench.pin else None,
        },
        "versions": {
            "cpython": platform.python_version(),
            "pypy": tool_version([args.pypy, "--version"]) if args.pypy else None,
            "mypyc": tool_version([args.mypyc, "--version"]) if args.mypyc else None,
            "pystachy_commit": git_commit(ROOT),
            "askme_commit": git_commit(args.askme) if args.askme else None,
            "curl": tool_version(["curl", "--version"]).split(" Release")[0][:60],
        },
        "port_files": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(source.glob("*.py"))
        },
        "runs": args.runs,
        "long_runs": long_runs,
        "steady": {"tasks": tasks, "steps": steps, "requests": len(steady["replay"])},
        "builds": builds,
        "verified_transcripts": verification,
        "suite_scenarios": list(scenarios),
        "suite_wall_median_ms": suite,
        "results": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(report, indent=1) + "\n")
    print(f"wrote {out.with_suffix('.json')}")
    shutil.rmtree(work, ignore_errors=True)
    return 0


def _cpu_model():
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


if __name__ == "__main__":
    sys.exit(main())
