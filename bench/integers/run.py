"""Integer benchmarks: Pystachy's explicit mpz and checked int64 against CPython and PyPy,
and Pystachy's promoting int once it exists. See README.md.

Each program prints a checksum, then the seconds of its timed loop (startup,
compilation and printing excluded). Every variant must print the same checksum
before any timing counts. Variants of a workload alternate order between
samples; peak RSS is the child's ru_maxrss, which a small C launcher reads (see
LAUNCHER).

usage: python3 bench/integers/run.py [--compiler ./pystachy] [--cpython python3]
           [--pypy PATH] [--python-int] [--samples 5] [--cpu N] [--json OUT] [--only NAME...]
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
# workload: (argument, explicit-mpz variant, checked-int64 variant)
WORKLOADS = {
    "lcg32": ("3000000", False, True),
    "collatz": ("100000", False, True),
    "cross64": ("5000000", True, False),
    "arith128": ("8000000", True, False),
    "factorial": ("300", True, False),
    "fibadd": ("150", True, False),
    "bigmul": ("600", True, False),
    "dectext": ("400000", True, False),
    "modpow": ("3000", True, False),
    "containers": ("1000000", True, False),
}


def variants(name, python_int):
    """The Pystachy variants of a workload: (label, file suffix)."""
    _, has_mpz, has_i64 = WORKLOADS[name]
    out = [("pys-int", "")] if python_int else []
    if has_mpz:
        out.append(("pys-mpz", "_mpz"))
    if has_i64:
        out.append(("pys-i64", "_i64"))
    return out


# The launcher runs its arguments as its child and writes the child's peak RSS in KiB to stderr,
# as the last line. Linux's ru_maxrss keeps the larger of a process's RSS before and after its
# exec, so a child forked from the Python runner would report at least the runner's own pages; one
# forked from this small program starts with this program's few.
LAUNCHER = r"""
#include <stdio.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc, char **argv) {
  if (argc < 2) return 2;
  pid_t pid = fork();
  if (pid < 0) { perror("fork"); return 2; }
  if (pid == 0) { execvp(argv[1], argv + 1); perror(argv[1]); _exit(127); }
  int status;
  struct rusage ru;
  if (wait4(pid, &status, 0, &ru) < 0) { perror("wait4"); return 2; }
#ifdef __APPLE__
  long kib = ru.ru_maxrss / 1024; /* (bytes there) */
#else
  long kib = ru.ru_maxrss;
#endif
  fprintf(stderr, "peak-rss-kib %ld\n", kib);
  return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}
"""
RSS = "peak-rss-kib "


def launcher(tmp):
    """Build LAUNCHER in directory tmp with the C compiler $CC (default cc); its path."""
    cc = os.environ.get("CC") or shutil.which("cc") or shutil.which("clang")
    if cc is None:
        sys.exit("bench/integers/run.py needs a C compiler (cc, or $CC) for its peak-RSS launcher")
    src = Path(tmp) / "launch.c"
    src.write_text(LAUNCHER)
    exe = Path(tmp) / "launch"
    subprocess.run(cc.split() + ["-O2", "-o", str(exe), str(src)], check=True)
    return exe


def run(cmd, cpu, launch):
    """Run cmd through the launcher launch: its checksum, its seconds and its peak RSS in KiB."""
    full = (["taskset", "-c", str(cpu)] if cpu is not None else []) + [str(launch)] + cmd
    proc = subprocess.run(full, capture_output=True)
    err = proc.stderr.decode().splitlines()
    peak = int(err.pop()[len(RSS):]) if err and err[-1].startswith(RSS) else None
    lines = proc.stdout.decode().strip().splitlines()
    if proc.returncode != 0 or len(lines) < 2 or peak is None:
        raise RuntimeError(f"{' '.join(cmd)} failed ({proc.returncode}): {chr(10).join(err).strip()[-300:]}")
    return lines[0], float(lines[-1]), peak


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default="./pystachy")
    parser.add_argument("--cpython", default="python3")
    parser.add_argument("--pypy")
    parser.add_argument("--python-int", action="store_true",
                        help="also build NAME.py itself, whose ordinary ints need a compiler that promotes them")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--only", nargs="+", choices=sorted(WORKLOADS))
    args = parser.parse_args()
    if args.cpu is not None and shutil.which("taskset") is None:
        parser.error("--cpu needs taskset")
    tmp = Path(tempfile.mkdtemp(prefix="pystachy-integers."))
    report = {"compiler": args.compiler, "cpython": args.cpython, "pypy": args.pypy,
              "python_int": args.python_int, "samples": args.samples, "workloads": {}}
    try:
        launch = launcher(tmp)
        for name in args.only or WORKLOADS:
            arg = WORKLOADS[name][0]
            cmds = {"cpython": [args.cpython, "-I", str(HERE / f"{name}.py"), arg]}
            if args.pypy:
                cmds["pypy"] = [args.pypy, "-I", str(HERE / f"{name}.py"), arg]
            for label, suffix in variants(name, args.python_int):
                exe = tmp / f"{name}{suffix}"
                subprocess.run(args.compiler.split() + ["build", str(HERE / f"{name}{suffix}.py"), "-o", str(exe)], check=True)
                cmds[label] = [str(exe), arg]
            checks = {label: run(cmd, args.cpu, launch)[0] for label, cmd in cmds.items()}
            if len(set(checks.values())) != 1:
                sys.exit(f"{name}: checksums differ: {checks}")
            samples = {label: [] for label in cmds}
            rss = {label: 0 for label in cmds}
            for i in range(args.samples):
                for label in (list(cmds) if i % 2 == 0 else list(reversed(cmds))):
                    check, seconds, peak = run(cmds[label], args.cpu, launch)
                    if check != checks[label]:
                        sys.exit(f"{name}/{label}: checksum changed")
                    samples[label].append(seconds)
                    rss[label] = max(rss[label], peak)
            base = statistics.median(samples["cpython"])
            row = {label: {"median": statistics.median(s), "samples": s, "rss_kib": rss[label]} for label, s in samples.items()}
            report["workloads"][name] = {"argument": arg, "checksum": checks["cpython"], "variants": row}
            cells = "  ".join(f"{label} {v['median']:.3f}s ({base / v['median']:.2f}x, {v['rss_kib'] / 1024:.0f} MiB)" for label, v in row.items())
            print(f"{name:11s} {cells}", flush=True)
    finally:
        shutil.rmtree(tmp)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
