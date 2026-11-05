"""Small native runtime-failure checks used by check_compiler_parallel.py."""
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def execute(command: list[str], environment: dict[str, str], timeout: float):
    process = subprocess.Popen(command, cwd=ROOT, env=environment, start_new_session=True,
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


def check_failures(compiler: list[str], base_env: dict[str, str], llvm: Path, timeout: float) -> int:
    """Return the number of scenarios whose jobs=1/jobs=2 failures agree.

    All C input deliberately fails preprocessing, so these cases compile no full
    runtime. A wrapper records real Clang launches: hidden secondary diagnostics
    alone cannot prove that the parallel path ran, or that custom flags stayed
    serial. Every child has a process-group watchdog.
    """
    llvm = llvm.resolve()
    cases = [
        ("both-invalid", "def broken(:\n", "", {1: 0, 2: 1}),
        ("only-c-invalid", '"minimal valid runtime"\n', "", {1: 1, 2: 1}),
        ("custom-flags-serial", "def broken(:\n", "-DPROBE", {1: 0, 2: 0}),
        ("asan-serial-order", '"minimal valid runtime"\n', "-fsanitize=address", {1: 2, 2: 2}),
    ]
    with tempfile.TemporaryDirectory(prefix="pystachy failure ' $; ") as temporary:
        root = Path(temporary)
        home = root / "home"
        home.mkdir()
        tools = root / "llvm"
        tools.mkdir()
        trace = root / "clang.log"
        for name in ("lib", "ryu", "mpz"):
            (home / name).symlink_to(ROOT / name, target_is_directory=True)
        for name in ("llvm-as", "llvm-link", "opt"):
            (tools / name).symlink_to(llvm / name)
        (tools / "clang").write_text('#!/bin/sh\nprintf \'%s\\n\' "$*" >> ' + shlex.quote(str(trace))
                                     + "\nexec " + shlex.quote(str(llvm / "clang")) + ' "$@"\n')
        (tools / "clang").chmod(0o755)
        program = root / "program.py"
        program.write_text("print(42)\n")
        for case, runtime, flags, counts in cases:
            (home / "runtime.py").write_text(runtime)
            (home / "runtime.c").write_text("#error C_SENTINEL\n")
            pair = []
            for jobs in (1, 2):
                cache = root / f"{case}-cache-{jobs}"
                scratch = root / f"{case}-tmp-{jobs}"
                scratch.mkdir()
                trace.write_text("")
                environment = dict(base_env, PYSTACHY_HOME=str(home), PYSTACHY_CACHE=str(cache),
                                   PYSTACHY_LLVM=str(tools), PYSTACHY_BUILD_JOBS=str(jobs),
                                   PYSTACHY_CFLAGS=flags, TMPDIR=str(scratch))
                result = execute(compiler + ["build", str(program), "-o", str(root / "output")],
                                 environment, timeout)
                calls = trace.read_text().splitlines()
                context = (case, jobs, result.returncode, result.stdout, result.stderr, calls)
                assert result.returncode == 1 and result.stdout == b"", context
                assert len(calls) == counts[jobs], context
                assert not list(scratch.iterdir()), (case, jobs, "left private scratch files")
                assert not list(cache.glob("*.bc*")), (case, jobs, "published a failed runtime")
                if case == "asan-serial-order":
                    assert " -x ir " in calls[0] and " -x c " in calls[1], context
                pair.append(result)
            assert pair[0].stderr == pair[1].stderr, (case, pair[0].stderr, pair[1].stderr)
            if case in ("both-invalid", "custom-flags-serial"):
                assert b"C_SENTINEL" not in pair[1].stderr, (case, pair[1].stderr)
                assert b"cannot build the runtime" not in pair[1].stderr, (case, pair[1].stderr)
            else:
                assert b"C_SENTINEL" in pair[1].stderr, (case, pair[1].stderr)
                assert b"cannot build the runtime" in pair[1].stderr, (case, pair[1].stderr)
            print(f"PASS {case}: jobs 1/2 diagnostics/status, launch counts and cleanup", flush=True)
    return len(cases)
