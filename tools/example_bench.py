"""Checked, bounded subprocess measurements shared by the example benchmarks.

The first command is the CPython oracle. Warm-ups, every timed repetition and
the separate RSS processes must agree before a comparison can be reported.
These checks validate evidence; they impose no performance threshold.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
import re
import shlex
import signal
import statistics
import subprocess
import sys
import time

TIMEOUT = 300


def positive_int(value, name: str = "runs") -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{name} must be a positive integer")
    try:
        result = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if result < 1:
        raise ValueError(f"{name} must be a positive integer")
    return result


def number(value, name: str, *, zero_ok: bool = False) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0 or (result == 0 and not zero_ok):
        bound = "nonnegative" if zero_ok else "positive"
        raise ValueError(f"{name} must be finite and {bound}: {value!r}")
    return result


def parse_timings(report: bytes | str, labels: tuple[str, ...], *, unit: str = "s",
                  zero_ok: tuple[str, ...] = ()) -> dict[str, float]:
    if isinstance(report, bytes):
        report = report.decode("ascii")
    pattern = ", ".join(re.escape(label) + r" (\S+) " + re.escape(unit) for label in labels)
    match = re.fullmatch(pattern + "\n?", report)
    if not match:
        raise ValueError(f"invalid timing report: {report!r}")
    return {label: number(value, f"{label} time", zero_ok=label in zero_ok)
            for label, value in zip(labels, match.groups())}


def child_cpu() -> float:
    import resource
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


@dataclass
class Run:
    stdout: bytes | None
    wall_s: float
    cpu_s: float | None
    timings: dict[str, float]


def execute(cmd: list[str], *, stdout=subprocess.PIPE, timeout: float = TIMEOUT) -> subprocess.CompletedProcess:
    """Own a process group so a timed-out compiler cannot leave LLVM children running."""
    with subprocess.Popen(cmd, stdout=stdout, stderr=subprocess.PIPE, start_new_session=True) as process:
        try:
            output, diagnostics = process.communicate(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
    return subprocess.CompletedProcess(cmd, process.returncode, output, diagnostics)


def run(cmd: list[str], *, expected: bytes | None = None, status: int = 0,
        expected_stderr: bytes = b"",
        timing_labels: tuple[str, ...] = (), zero_ok: tuple[str, ...] = (),
        cpu: bool = False, stdout=subprocess.PIPE, timeout: float = TIMEOUT) -> Run:
    timeout = number(timeout, "timeout")
    if timing_labels and expected_stderr:
        raise ValueError("timing reports and fixed stderr require separate commands")
    before_cpu = child_cpu() if cpu else 0.0
    start = time.perf_counter()
    result = execute(cmd, stdout=stdout, timeout=timeout)
    # Do not include comparison/hash/parsing work in the measured process time.
    wall_s = time.perf_counter() - start
    cpu_s = child_cpu() - before_cpu if cpu else None
    if result.returncode != status:
        raise RuntimeError(f"{shlex.join(cmd)}: exit {result.returncode}, expected {status}\n"
                           f"{result.stderr.decode(errors='replace')}")
    if timing_labels:
        timings = parse_timings(result.stderr, timing_labels, zero_ok=zero_ok)
    elif result.stderr != expected_stderr:
        raise ValueError(f"unexpected stderr for {shlex.join(cmd)}: {result.stderr!r}")
    else:
        timings = {}
    if expected is not None and result.stdout != expected:
        raise ValueError(f"OUTPUT DIFFERS for {shlex.join(cmd)}")
    number(wall_s, "wall time")
    if cpu_s is not None:
        number(cpu_s, "CPU time")
    return Run(result.stdout, wall_s, cpu_s, timings)


# A fresh supervisor keeps the benchmark driver's high-water mark out of the
# child's RSS. Return a digest rather than copying large reports into JSON.
RSS_PROBE = """
import hashlib, json, resource, subprocess, sys
p = subprocess.run(sys.argv[1:], capture_output=True)
print(json.dumps([resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                  p.returncode, len(p.stdout), hashlib.sha256(p.stdout).hexdigest(),
                  p.stderr.decode()]))
"""


def peak_rss(cmd: list[str], expected: bytes, *, status: int = 0,
             expected_stderr: bytes = b"",
             timeout: float = TIMEOUT) -> int:
    timeout = number(timeout, "timeout")
    # The outer deadline owns both supervisor and child, including descendants.
    probe = run([sys.executable, "-I", "-c", RSS_PROBE, *cmd], timeout=timeout)
    fields = json.loads(probe.stdout)
    if not isinstance(fields, list) or len(fields) != 5:
        raise ValueError(f"invalid RSS report for {shlex.join(cmd)}: {fields!r}")
    raw, code, size, digest, stderr = fields
    if type(code) is not int or code != status:
        raise RuntimeError(f"RSS run for {shlex.join(cmd)}: exit {code}, expected {status}\n{stderr}")
    if not isinstance(stderr, str) or stderr != expected_stderr.decode():
        raise ValueError(f"unexpected stderr in RSS run for {shlex.join(cmd)}: {stderr!r}")
    if type(size) is not int or size != len(expected) or digest != hashlib.sha256(expected).hexdigest():
        raise ValueError(f"OUTPUT DIFFERS in RSS run for {shlex.join(cmd)}")
    if type(raw) is not int or raw <= 0:
        raise ValueError(f"invalid peak RSS: {raw!r}")
    kib = raw // 1024 if sys.platform == "darwin" else raw
    number(kib, "peak RSS")
    return kib


@dataclass
class Measurement:
    wall_s: float
    cpu_s: float | None
    rss_kib: int | None
    timings: dict[str, float]
    stdout: bytes


def measure_pair(commands: list[list[str]], runs: int, *, status: int = 0,
                 expected_stderr: bytes = b"",
                 timed_commands: list[list[str]] | None = None,
                 timing_labels: tuple[str, ...] = (), zero_ok: tuple[str, ...] = (),
                 cpu: bool = False, rss: bool = True, timeout: float = TIMEOUT) -> list[Measurement]:
    runs = positive_int(runs)
    if not commands or (timed_commands is not None and len(timed_commands) != len(commands)):
        raise ValueError("expected matching nonempty command lists")
    if timing_labels and timed_commands is None:
        raise ValueError("timing labels require timed commands")
    timed = commands if timed_commands is None else timed_commands
    # Validate CPython and every native command before collecting measurements.
    expected = run(commands[0], status=status, expected_stderr=expected_stderr, timeout=timeout).stdout
    for cmd in commands[1:]:
        run(cmd, expected=expected, status=status, expected_stderr=expected_stderr, timeout=timeout)
    if timed_commands is not None:
        for cmd in timed:
            run(cmd, expected=expected, status=status, expected_stderr=expected_stderr, timing_labels=timing_labels,
                zero_ok=zero_ok, timeout=timeout)
    walls: list[list[float]] = [[] for _ in commands]
    cpus: list[list[float]] = [[] for _ in commands]
    phases: list[dict[str, list[float]]] = [{label: [] for label in timing_labels} for _ in commands]
    for repeat in range(runs):
        # Rotate order so transient load does not always affect one runtime first.
        order = range(len(commands)) if repeat % 2 == 0 else range(len(commands) - 1, -1, -1)
        for index in order:
            sample = run(timed[index], expected=expected, status=status, expected_stderr=expected_stderr,
                         timing_labels=timing_labels,
                         zero_ok=zero_ok, cpu=cpu, timeout=timeout)
            walls[index].append(sample.wall_s)
            if cpu:
                cpus[index].append(sample.cpu_s)
            for label in timing_labels:
                phases[index][label].append(sample.timings[label])
    return [Measurement(statistics.median(walls[index]), statistics.median(cpus[index]) if cpu else None,
                        peak_rss(cmd, expected, status=status, expected_stderr=expected_stderr, timeout=timeout) if rss else None,
                        {label: statistics.median(values) for label, values in phases[index].items()}, expected)
            for index, cmd in enumerate(commands)]
