"""Optional native compiler-parallelism integration checks; no timing thresholds.

Run after rebuilding the compiler:
  python3 tools/check_compiler_parallel.py --compiler ./pystachy [--lto]

The LTO checks require Linux and matching LLVM 18 clang/LLD. Each child has a
watchdog and an isolated process group; each build has private scratch and cache.
"""
import argparse
from collections import Counter
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = '''import math
import sys
from typing import Iterator

class Value:
    def __init__(self, n: int) -> None:
        self.n = n

class Owner:
    def __init__(self, value: Value) -> None:
        self.value = value

values = [Value(i) for i in range(64)]
owner = Owner(values[13])
held = (values[17],)
noise = [str(i) + "!" for i in range(128)]
print("kept", sum([v.n for v in values]), owner.value.n, held[0].n, noise[-1])

def numbers(n: int) -> Iterator[int]:
    try:
        for i in range(n):
            yield i * 2
    finally:
        print("finally")

print("yield", list(numbers(5)))

def checked(n: int) -> int:
    if n < 0:
        raise ValueError("negative")
    return n * 3

try:
    for n in [2, -1, 4]:
        print("value", checked(n))
except ValueError as error:
    print("caught", str(error))

for arg in sys.argv[1:]:
    x = float(arg)
    y = x * 1.0
    print("float", x, y, math.copysign(1.0, y), x == x, (x * x + 0.5) * 0.25 - x)
'''
FLOAT_ARGS = ["-0.0", "0.0", "1.25", "-3.5", "1e-300", "inf", "nan"]
PREFIX = b"pystachy-timing\t"


def execute(command, env, timeout):
    process = subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def successful(result):
    assert result.returncode == 0, (shlex.join(result.args), result.returncode, result.stderr.decode(errors="replace"))


def stage_counts(result):
    stages = Counter()
    for line in result.stderr.splitlines():
        assert line.startswith(PREFIX), line.decode(errors="replace")
        prefix, name, elapsed = line.split(b"\t")
        assert prefix == PREFIX.rstrip(b"\t") and float(elapsed) >= 0, line
        stages[name.decode()] += 1
    return stages


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"), help="native compiler command, shell-quoted arguments")
    parser.add_argument("--python", default=sys.executable, help="CPython oracle command; use the repository's pinned version")
    parser.add_argument("--llvm", type=Path, default=Path(os.getenv("PYSTACHY_LLVM", "/usr/lib/llvm-18/bin")))
    parser.add_argument("--timeout", type=float, default=300, help="watchdog seconds per command")
    parser.add_argument("--lto", action="store_true", help="also check LTO partitions 1, 2 and 4 under collection on every allocation")
    args = parser.parse_args()
    compiler, python = shlex.split(args.compiler), shlex.split(args.python)
    if not compiler or not python or args.timeout <= 0:
        parser.error("compiler/Python commands must be nonempty and timeout must be positive")
    if os.name != "posix" or (args.lto and sys.platform != "linux"):
        parser.error("native driver checks require POSIX; the LTO prototype requires Linux")
    llvm = args.llvm.resolve()
    for name in ("clang", "opt", "llvm-link", "llvm-as") + (("ld.lld",) if args.lto else ()):
        if not (llvm / name).is_file():
            parser.error(f"missing LLVM tool: {llvm / name}")
    base = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")
            and key not in ("PYTHONPATH", "PYTHONHOME", "LD_PRELOAD")}
    base["PYSTACHY_LLVM"] = str(llvm)
    from compiler_parallel_failures import check_failures
    failures = check_failures(compiler, base, llvm, args.timeout)
    builds = 0
    with tempfile.TemporaryDirectory(prefix="pystachy native parallel ' $; ") as temporary:
        root = Path(temporary)
        home = root / "home"
        home.mkdir()
        for name in ("runtime.c", "runtime.py"):
            shutil.copyfile(ROOT / name, home / name)
        for name in ("lib", "ryu", "mpz"):
            (home / name).symlink_to(ROOT / name, target_is_directory=True)
        env = dict(base, PYSTACHY_HOME=str(home))
        source = root / "probe.py"
        source.write_text(SOURCE)
        oracle = execute(python + [str(source), *FLOAT_ARGS], env, args.timeout)
        successful(oracle)
        assert oracle.stderr == b"", oracle.stderr

        # The worker must consume the snapshot while retaining the diagnostic source
        # identity. Changing the live source is a negative control against rereading it.
        original, snapshot = home / "runtime.py", root / "snapshot.py"
        runtime_bytes = original.read_bytes()
        snapshot.write_bytes(runtime_bytes)
        direct, worker = root / "direct.ll", root / "worker.ll"
        scratch = root / "snapshot-tmp"
        scratch.mkdir()
        snapshot_env = dict(env, TMPDIR=str(scratch))
        result = execute(compiler + ["rt", str(original), "-o", str(direct)], snapshot_env, args.timeout)
        successful(result)
        assert result.stdout == result.stderr == b"", (result.stdout, result.stderr)
        original.write_text("def broken(:\n")
        try:
            result = execute(compiler + ["rt-cache", str(snapshot), str(original), "-o", str(worker)], snapshot_env, args.timeout)
            successful(result)
            assert result.stdout == result.stderr == b"", (result.stdout, result.stderr)
            assert worker.read_bytes() == direct.read_bytes(), "rt-cache changed runtime IR or read the live file"
            assert not list(scratch.iterdir()), "runtime worker left scratch files"
        finally:
            original.write_bytes(runtime_bytes)
        print("PASS native runtime snapshot: identical IR with changed live source", flush=True)

        def build(label, jobs, cache, partitions=0):
            nonlocal builds
            scratch = root / (label + "-tmp")
            scratch.mkdir()
            executable = root / label
            buildenv = dict(env, PYSTACHY_CACHE=str(cache), TMPDIR=str(scratch), PYSTACHY_TIMING="1",
                            PYSTACHY_BUILD_JOBS=str(jobs), PYSTACHY_LTO_PARTITIONS=str(partitions))
            result = execute(compiler + ["build", str(source), "-o", str(executable)], buildenv, args.timeout)
            successful(result)
            assert result.stdout == b"", result.stdout
            counts = stage_counts(result)
            assert counts["driver.total"] == 1, counts
            assert not list(scratch.iterdir()), f"{label}: build left scratch files"
            assert len(list(cache.glob("runtime-py-*.bc"))) == 1, f"{label}: missing coherent runtime cache entry"
            for stress in ("0", "1"):
                actual = execute([str(executable), *FLOAT_ARGS], dict(env, PYSTACHY_GC_STRESS=stress), args.timeout)
                assert (actual.returncode, actual.stdout, actual.stderr) == (oracle.returncode, oracle.stdout, oracle.stderr), (
                    label, stress, actual.returncode, actual.stdout, actual.stderr, oracle.stdout)
            builds += 1
            print(f"PASS {label}: CPython output/status under ordinary and every-allocation GC", flush=True)
            return counts

        serial = build("cold-serial", 1, root / "cache-serial")
        assert serial["runtime.c"] == serial["runtime.frontend"] == 1 and serial["runtime.parallel"] == 0, serial
        cache = root / "cache-parallel"
        parallel = build("cold-parallel", 2, cache)
        assert parallel["runtime.parallel"] == parallel["driver.runtime_worker"] == 1 and parallel["runtime.c"] == 0, parallel
        warm = build("warm-parallel", 2, cache)
        assert {name for name in warm if name.startswith("runtime.")} == {"runtime.cache_lookup"}, warm
        assert warm["driver.runtime_worker"] == 0, warm
        if args.lto:
            for partitions in (1, 2, 4):
                counts = build(f"lto-{partitions}", 4, cache, partitions)
                assert counts["program.lto_codegen_link"] == 1 and counts["runtime.parallel"] == 0, counts
    print(f"PASS compiler parallelism: {failures} failure cases, snapshot parity, {builds} native builds")


if __name__ == "__main__":
    main()
