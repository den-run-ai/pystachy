"""Bounded checks of real example entry points, with the pinned CPython as oracle.

The corpus also checks the examples' helpers. Here file loading, argument parsing,
stdout, stderr and exit status run through the actual command lines, JIT and AOT.
The existing JSON repair process and agent loopback-HTTP checks run unchanged, and the
recorded JSON repair corpus is replayed through native JIT and AOT builds of the port.
"""
import argparse
from contextlib import nullcontext
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import runpy
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODES = ["cpython", "jit", "aot"]


@dataclass(frozen=True)
class Case:
    name: str
    args: tuple[str, ...]
    status: int = 0


# Only tiny, deterministic inputs; options that print elapsed time are excluded.
# An empty router batch has a defined zero-time report, so it can check --in-memory.
CASES = {
    "csvstat": [Case("table", ("data.csv",)), Case("csv", ("data.csv", "--csv")),
                Case("delimiter", ("data.scsv", "-d", ";", "--csv")), Case("usage", (), 2)],
    "latency": [Case("report", ("latency.log",)), Case("usage", (), 2)],
    "mailmerge": [Case("substitute", ("notice.txt", "people.tsv")),
                  Case("split", ("notice.txt", "people.tsv", "--split")),
                  Case("safe", ("missing.txt", "people.tsv", "--safe")),
                  Case("missing-field", ("missing.txt", "people.tsv"), 1), Case("usage", (), 2)],
    "topk": [Case("heap", ("text.txt", "3")), Case("sort", ("text.txt", "3", "--sort")),
             Case("zero", ("text.txt", "0")), Case("usage", (), 2)],
    "urlstats": [Case("report", ("--top", "2", "urls.log")),
                 Case("canonical", ("--canon", "urls.log")), Case("usage", (), 2)],
    "route": [Case("cache", ("rules.txt", "events.tsv", "--names")),
              Case("uncached", ("rules.txt", "events.tsv", "--no-cache", "--names")),
              Case("fnmatch", ("rules.txt", "events.tsv", "--fnmatch", "--names")),
              Case("empty-memory", ("rules.txt", "empty.tsv", "--in-memory", "--names")),
              Case("conflicting-options", ("rules.txt", "events.tsv", "--fnmatch", "--no-cache"), 2),
              Case("usage", (), 2)],
}


def fixtures(directory):
    files = {
        "data.csv": 'id,amount,name,empty\r\n1,1.5,"café, tea",\r\n2,2.5,"two\nlines",\r\n'
                    '3,,plain,,extra\r\n4\r\n',
        "data.scsv": 'id;name\n9007199254740993;"semi;colon"\n9007199254740995;plain\n',
        "latency.log": '2026-10-13T08:00:00 GET /a 200 1.0 10\n'
                       '2026-10-13T08:00:01 GET /a 503 3.0 30\n'
                       '2026-10-13T08:00:02 POST /b 200 2.0 0\n'
                       '2026-10-13T08:00:03 POST /b 200 4.0 0\n'
                       '2026-10-13T08:00:04 GET /a 504 - 0\ninvalid log line\n',
        "notice.txt": 'To: $name <$email>\n\nHello ${name}. Message $seq/$count: $$5.\nFrom sender\n',
        "missing.txt": 'Hello $name, $unknown. Message $seq/$count.\n',
        "people.tsv": 'name\temail\nZoë\tzoe@example.com\nAda\tada@example.com\n',
        "text.txt": 'Tea, café tea. apple!\nApple tea café pear; pear.\n--\n',
        "urls.log": '127.0.0.1 - - [date] "GET /caf%C3%A9?b=2&a=1 HTTP/1.1" 200 1\n'
                    '127.0.0.1 - - [date] "GET /caf%c3%a9?a=1&b=2 HTTP/1.1" 200 1\n'
                    '127.0.0.1 - - [date] "GET /a%2Fb?q=%FF&q=&x=+ HTTP/1.1" 200 1\ninvalid\n',
        "rules.txt": '# first matching rule wins\napi.* web\ndb.[ab] data\napi.* shadowed\n',
        "events.tsv": 'api.read\t1\ndb.a\t2\nother\t3\napi.read\t4\ndb.b\t5\n',
        "empty.tsv": '',
    }
    for name, value in files.items():
        (directory / name).write_bytes(value.encode("utf-8"))
    return {name: value.encode("utf-8") for name, value in files.items()}


def environment(cache):
    env = {key: value for key, value in os.environ.items()
           if (not key.startswith("PYSTACHY_") or key == "PYSTACHY_LLVM") and
           key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE", "PYTHONINSPECT", "PYTHONSTARTUP"}}
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(cache), PYSTACHY_JOBS="2",
               PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
               PYTHONHASHSEED="0", LC_ALL="C", COLUMNS="80")
    return env


def detail(label, command, timeout, status, stdout, stderr):
    return (f"{label}: command={command!r}, timeout={timeout}s, exit={status}\n"
            f"stdout={stdout!r}\nstderr={stderr!r}")


def run(label, command, env, cwd, status=0, timeout=120, process_scope=None):
    """Kill the whole owned process group on timeout, including a driver's children.
    status=None leaves the exit status to the caller."""
    try:
        with subprocess.Popen(command, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=True) as process, \
                (process_scope(process) if process_scope is not None else nullcontext()):
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except BaseException as exc:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
                if isinstance(exc, subprocess.TimeoutExpired):
                    raise RuntimeError(detail(label, command, timeout, "timeout", stdout, stderr)) from exc
                raise
    except OSError as exc:
        raise RuntimeError(f"{label}: command={command!r}, timeout={timeout}s: {exc}") from exc
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if status is not None and result.returncode != status:
        raise RuntimeError(detail(label, command, timeout, result.returncode, stdout, stderr) +
                           f"\nexpected exit={status}")
    return result


def compare(label, actual, reference):
    if (actual.returncode, actual.stdout, actual.stderr) != (reference.returncode, reference.stdout, reference.stderr):
        raise ValueError(detail(label, actual.args, 120, actual.returncode, actual.stdout, actual.stderr) +
                         f"\nCPython exit={reference.returncode}, stdout={reference.stdout!r}, stderr={reference.stderr!r}")


def build(name, source, compiler, directory, env):
    exe = directory / name
    result = run(name + "/build", [str(compiler), "build", str(source), "-o", str(exe)], env, ROOT)
    if result.stdout or result.stderr or not exe.is_file() or not os.access(exe, os.X_OK):
        raise ValueError(detail(name + "/build", result.args, 120, result.returncode, result.stdout, result.stderr) +
                         "\nexpected a new executable and no build diagnostics")
    return str(exe)


def case_names():
    return [f"{example}/{case.name}" for example, cases in CASES.items() for case in cases]


REPAIR_MODES = ["jit", "aot"]


def integrations():
    # Read the trusted check's case list without invoking main, so adding a case updates the gate.
    repair_cases = runpy.run_path(str(ROOT / "tests/upstream/json_repair/cli.py"))["CASES"]
    replay_cases = json.loads((ROOT / "tests/upstream/json_repair/cases.json").read_text())
    return {"json_repair": len(repair_cases), "agent_http": MODES,
            "json_repair_replay": {"cases": len(replay_cases), "modes": REPAIR_MODES}}


def validate_report(report):
    expected = {"schema": 1, "result": "pass", "python": (ROOT / ".python-version").read_text().strip(),
                "modes": MODES, "cases": case_names(), "integrations": integrations()}
    if (not isinstance(report, dict) or type(report.get("schema")) is not int or
            any(report.get(key) != value for key, value in expected.items()) or report.get("error") or
            type(report["integrations"]["json_repair"]) is not int or
            type(report["integrations"]["json_repair_replay"]["cases"]) is not int):
        raise ValueError("example-cli: missing, duplicated or incomplete CPython/JIT/AOT checks")


def check(compiler, cache, report):
    env = environment(cache)
    with tempfile.TemporaryDirectory(prefix="pystachy-example-cli-") as temporary:
        directory = Path(temporary)
        inputs = directory / "inputs"
        inputs.mkdir()
        original = fixtures(inputs)
        for example, cases in CASES.items():
            source = ROOT / "examples" / example / (example + ".py")
            exe = build(example, source, compiler, directory, env)
            for case in cases:
                name = f"{example}/{case.name}"
                commands = [[sys.executable, str(source)], [str(compiler), "run", str(source)], [exe]]
                reference = None
                for mode, command in zip(MODES, commands, strict=True):
                    label = name + "/" + mode
                    result = run(label, command + list(case.args), env, inputs, status=case.status)
                    if mode == "cpython":
                        if not (result.stdout if case.status == 0 else result.stderr):
                            raise ValueError(detail(label, result.args, 120, result.returncode, result.stdout, result.stderr) +
                                             "\nCPython oracle did not exercise the entry point")
                        reference = result
                    else:
                        compare(label, result, reference)
                    observed = {path.name: path.read_bytes() if path.is_file() else None for path in inputs.iterdir()}
                    if observed != original:
                        changed = sorted(name for name in original.keys() | observed.keys()
                                         if original.get(name) != observed.get(name))
                        raise ValueError(detail(label, result.args, 120, result.returncode, result.stdout, result.stderr) +
                                         f"\nexample changed input files: {changed!r}")
                report["cases"].append(name)
                print(f"ok {name}: CPython/JIT/AOT exit, stdout and stderr", flush=True)

        count = integrations()["json_repair"]
        result = run("json_repair/cli", [sys.executable, str(ROOT / "tests/upstream/json_repair/cli.py"),
                                        str(compiler)], env, ROOT, timeout=300)
        expected = f"json_repair CLI: {count} process cases matched CPython {report['python']} in JIT and AOT\n".encode()
        if result.stdout != expected or result.stderr:
            raise ValueError(detail("json_repair/cli", result.args, 300, result.returncode, result.stdout, result.stderr) +
                             f"\nexpected stdout={expected!r}, stderr=b''")
        report["integrations"]["json_repair"] = count
        print(result.stdout.decode(), end="", flush=True)
        replay_json_repair(compiler, env, directory, report)

        source = ROOT / "examples/agent/agent.py"
        exe = build("agent", source, compiler, directory, env)
        requests = len(json.loads((ROOT / "examples/agent/fixtures/repair.json").read_text()))
        launchers = [[sys.executable, str(source)], [str(compiler), "run", str(source)], [exe]]
        report["integrations"]["agent_http"] = []
        for mode, launcher in zip(MODES, launchers, strict=True):
            label = "agent/http/" + mode
            result = run(label, [sys.executable, str(ROOT / "examples/agent/http_smoke.py"), "--", *launcher], env, ROOT)
            expected = (f"HTTP smoke passed: {requests} validated requests; checked repair; launcher=" +
                        " ".join(launcher) + "\n").encode()
            if not result.stdout.endswith(expected) or result.stderr:
                raise ValueError(detail(label, result.args, 120, result.returncode, result.stdout, result.stderr) +
                                 f"\nexpected final line={expected!r}, stderr=b''")
            report["integrations"]["agent_http"].append(mode)
            print(f"ok {label}: {requests} loopback requests and checked repair", flush=True)


def replay_json_repair(compiler, env, directory, report):
    """The recorded JSON repair corpus through native JIT and AOT builds of the port, checked
    against the pinned-CPython outcomes in cases.json by the corpus checker."""
    count = integrations()["json_repair_replay"]["cases"]
    replay = ROOT / "tests/upstream/json_repair/replay.py"
    checker = ROOT / "tools/json_repair_parity.py"
    inputs = directory / "json_repair_inputs.jsonl"
    run("json_repair/replay/inputs", [sys.executable, str(checker), "--write-inputs", str(inputs)], env, ROOT)
    port = dict(env, PYSTACHY_PATH=str(ROOT / "ports"))
    exe = build("json_repair_replay", replay, compiler, directory, port)
    commands = {"jit": [str(compiler), "run", str(replay), str(inputs)], "aot": [exe, str(inputs)]}
    report["integrations"]["json_repair_replay"] = {"cases": count, "modes": []}
    expected = f"{count}/{count} match; 0 problems\n".encode()
    for mode in REPAIR_MODES:
        label = "json_repair/replay/" + mode
        result = run(label, commands[mode], port, ROOT, timeout=300)
        if result.stderr:
            raise ValueError(detail(label, result.args, 300, result.returncode, b"<replay output>", result.stderr) +
                             "\nexpected stderr=b''")
        output = directory / f"json_repair_{mode}.out"
        output.write_bytes(result.stdout)
        checked = run(label + "/check", [sys.executable, str(checker), str(output)], env, ROOT, status=None)
        if (checked.returncode, checked.stdout, checked.stderr) != (0, expected, b""):
            raise ValueError(detail(label + "/check", checked.args, 120, checked.returncode, checked.stdout[:4000],
                                    checked.stderr) + f"\nexpected stdout={expected!r}, stderr=b''")
        report["integrations"]["json_repair_replay"]["modes"].append(mode)
        print(f"ok {label}: {count}/{count} recorded cases match CPython {report['python']}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "pystachy", help="verified native compiler")
    parser.add_argument("--cache", type=Path, default=ROOT / "build", help="runtime cache shared by these checks")
    parser.add_argument("--json", type=Path, default=ROOT / "build/example-cli-smoke.json")
    args = parser.parse_args(argv)
    report = {"schema": 1, "result": "running", "python": platform.python_version(),
              "modes": MODES, "cases": [], "integrations": {}}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n")
    try:
        pinned = (ROOT / ".python-version").read_text().strip()
        if platform.python_implementation() != "CPython" or platform.python_version() != pinned:
            raise ValueError(f"Use CPython {pinned} for the CLI oracle")
        check(args.compiler.resolve(), args.cache.resolve(), report)
        report["result"] = "pass"
        validate_report(report)
    except (OSError, RuntimeError, ValueError) as exc:
        report.update(result="fail", error=str(exc))
        print(str(exc), file=sys.stderr)
    args.json.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
