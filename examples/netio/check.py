"""Differential socket/readiness prototype check against an independent stdlib oracle."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "probe.py"
CASES = (
    "lifecycle", "binary", "selector_keys", "readiness", "backpressure", "tcp",
    "blocking_connect", "refused", "timeouts", "fd_reuse", "closed_errors", "inherited_pipe",
)
CPYTHON_MODES = ("cpython_oracle", "cpython_bridge")
NATIVE_MODES = ("jit", "aot", "jit_gc", "aot_gc")
SOURCES = ("netio.c", "netio.h", "netio.py", "probe.py", "oracle/netio.py", "check.py")


def environment(directory: Path, oracle: bool = False) -> dict[str, str]:
    """Use private caches and explicit module/library paths, independent of a caller's settings."""
    env = {key: value for key, value in os.environ.items()
           if (not key.startswith("PYSTACHY_") or key == "PYSTACHY_LLVM")
           and key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE", "PYTHONINSPECT", "PYTHONSTARTUP"}}
    modules = [str(HERE / "oracle")] if oracle else [str(HERE), str(ROOT / "tools" / "rt_cpython")]
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_PATH=str(HERE),
               PYSTACHY_CACHE=str(directory / "cache"), PYSTACHY_PROGRAM_CACHE="0", PYSTACHY_JOBS="2",
               PYTHONPATH=os.pathsep.join(modules), PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONUTF8="1", PYTHONHASHSEED="0", LC_ALL="C", COLUMNS="80")
    for name in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        env[name] = str(directory) + (os.pathsep + env[name] if env.get(name) else "")
    return env


def detail(label, command, timeout, status, stdout, stderr):
    return (f"{label}: command={command!r}, timeout={timeout}s, exit={status}\n"
            f"stdout={stdout!r}\nstderr={stderr!r}")


def run(label, command, env, cwd, *, timeout=30, pass_fds=()):
    """Bound the complete owned process group, retaining diagnostics on timeout/failure."""
    try:
        with subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=True, pass_fds=pass_fds) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except BaseException as error:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
                if isinstance(error, subprocess.TimeoutExpired):
                    raise RuntimeError(detail(label, command, timeout, "timeout", stdout, stderr)) from error
                raise
    except OSError as error:
        raise RuntimeError(f"{label}: command={command!r}: {error}") from error
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if result.returncode:
        raise RuntimeError(detail(label, command, timeout, result.returncode, stdout, stderr))
    return result


def compare(label, actual, reference):
    observed = actual.returncode, actual.stdout, actual.stderr
    expected = reference.returncode, reference.stdout, reference.stderr
    if observed != expected:
        raise ValueError(f"{label}: differs from independent CPython stdlib oracle\n"
                         f"expected={expected!r}\nactual={observed!r}")


def quiet(label, result):
    if result.stdout or result.stderr:
        raise ValueError(f"{label}: unexpected build diagnostics: {result.stdout!r}, {result.stderr!r}")


def compiler_command(value: str) -> list[str]:
    """Keep checkout-relative executables and hosted scripts valid in private cwd."""
    command = shlex.split(value)
    if not command:
        raise ValueError("--compiler must not be empty")
    return [str((ROOT / word).resolve())
            if (not index or command[index - 1] not in ("-m", "-c")) and (ROOT / word).is_file()
            else word for index, word in enumerate(command)]


def c_compiler(value: str | None, env: dict[str, str]) -> list[str]:
    if value is not None:
        command = shlex.split(value)
        if not command:
            raise ValueError("--cc must not be empty")
        return command
    llvm = env.get("PYSTACHY_LLVM")
    if llvm and (Path(llvm) / "clang").is_file():
        return [str(Path(llvm) / "clang")]
    executable = shutil.which("cc", path=env.get("PATH"))
    if executable is None:
        raise RuntimeError("a C11 compiler is required; provide --cc or PYSTACHY_LLVM")
    return [executable]


def build_bridge(directory, env, cc, timeout):
    output = directory / "libpystachy_netio.so"
    linkage = "-dynamiclib" if sys.platform == "darwin" else "-shared"
    command = cc + ["-std=c11", "-O2", "-g", "-fPIC", linkage, "-Wall", "-Wextra", "-Werror",
                    "-Wpedantic", str(HERE / "netio.c"), "-o", str(output)]
    quiet("bridge/build", run("bridge/build", command, env, ROOT, timeout=timeout))
    if not output.is_file() or output.stat().st_size == 0:
        raise ValueError("bridge/build: compiler did not create the shared library")
    return output


@contextlib.contextmanager
def inherited_pipe():
    """A real inherited readable pipe above select's FD_SETSIZE, with explicit ownership."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    needed = 2050
    if soft < needed:
        if hard != resource.RLIM_INFINITY and hard < needed:
            raise RuntimeError("inherited_pipe requires a descriptor limit of at least 2050")
        resource.setrlimit(resource.RLIMIT_NOFILE, (needed, hard))
    read_fd = write_fd = high_fd = -1
    try:
        read_fd, write_fd = os.pipe()
        high_fd = fcntl.fcntl(read_fd, fcntl.F_DUPFD, 2048)
        os.close(read_fd)
        read_fd = -1
        if os.write(write_fd, b"hi\x00\xff\n") != 5:
            raise RuntimeError("inherited_pipe fixture write was incomplete")
        os.close(write_fd)
        write_fd = -1
        yield high_fd
    finally:
        for fd in (read_fd, write_fd, high_fd):
            if fd >= 0:
                os.close(fd)
        if soft < needed:
            resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def scenario(label, command, case, repeat, env, directory, timeout):
    args = command + [case, str(repeat)]
    if case == "inherited_pipe":
        with inherited_pipe() as fd:
            return run(label, args + [str(fd)], env, directory, timeout=timeout, pass_fds=(fd,))
    return run(label, args, env, directory, timeout=timeout)


def hashes():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in SOURCES}


def validate_report(report, cpython_only=False):
    modes = list(CPYTHON_MODES + (() if cpython_only else NATIVE_MODES))
    if (not isinstance(report, dict) or type(report.get("schema")) is not int or report["schema"] != 1
            or report.get("result") != "pass" or report.get("error")
            or report.get("python") != (ROOT / ".python-version").read_text().strip()
            or report.get("modes") != modes or report.get("cases") != list(CASES)
            or type(report.get("repeat")) is not int or report["repeat"] < 1
            or not isinstance(report.get("runs"), dict) or set(report["runs"]) != set(modes)):
        raise ValueError("netio: missing or incomplete differential validation")
    for mode in modes:
        if report["runs"][mode].get("cases") != list(CASES):
            raise ValueError(f"netio: incomplete {mode} scenarios")


def check(args, report):
    pinned = (ROOT / ".python-version").read_text().strip()
    if platform.python_version() != pinned:
        raise RuntimeError(f"use pinned CPython {pinned}; running {platform.python_version()}")
    if sys.platform not in ("linux", "darwin"):
        raise RuntimeError("this prototype check supports Linux and macOS only")
    compiler = compiler_command(args.compiler)
    before = hashes()
    report.update(python=platform.python_version(), platform=platform.platform(), source_sha256=before,
                  repeat=args.repeat, compiler=compiler, cases=list(CASES), runs={}, modes=[])
    with tempfile.TemporaryDirectory(prefix="pystachy-netio-") as temporary:
        directory = Path(temporary)
        # A private copy avoids CPython's script-directory precedence loading the bridge
        # during oracle runs. Every mode receives these identical, hashed source bytes.
        source = directory / "probe.py"
        source.write_bytes(SOURCE.read_bytes())
        env = environment(directory)
        oracle_env = environment(directory, oracle=True)
        cc = c_compiler(args.cc, env)
        library = build_bridge(directory, env, cc, args.build_timeout)
        report.update(c_compiler=cc, library_sha256=hashlib.sha256(library.read_bytes()).hexdigest())
        expected = {}
        for case in CASES:
            result = scenario("cpython_oracle/" + case, [sys.executable, str(source)], case,
                              args.repeat, oracle_env, directory, args.timeout)
            marker = f"{case} {args.repeat} ok\n".encode()
            if result.stdout != marker or result.stderr:
                raise ValueError(f"cpython_oracle/{case}: scenario did not finish cleanly: "
                                 f"{result.stdout!r}, {result.stderr!r}")
            expected[case] = result
        report["modes"].append("cpython_oracle")
        report["runs"]["cpython_oracle"] = {"cases": list(CASES)}
        print(f"cpython_oracle: {len(CASES)} scenarios passed", flush=True)
        modes = [("cpython_bridge", [sys.executable, str(source)], {})]
        if not args.cpython_only:
            executable = directory / "probe"
            result = run("native/build", compiler + ["build", str(source), "-o", str(executable)],
                         env, ROOT, timeout=args.build_timeout)
            quiet("native/build", result)
            if not executable.is_file() or not os.access(executable, os.X_OK):
                raise ValueError("native/build: compiler did not create a fresh executable")
            modes += [
                ("jit", compiler + ["run", str(source)], {}),
                ("aot", [str(executable)], {}),
                ("jit_gc", compiler + ["run", str(source)], {"PYSTACHY_GC_STRESS_PROGRAM": str(args.stress)}),
                ("aot_gc", [str(executable)], {"PYSTACHY_GC_STRESS": str(args.stress)}),
            ]
        for mode, command, settings in modes:
            completed = []
            for case in CASES:
                actual = scenario(mode + "/" + case, command, case, args.repeat, env | settings,
                                  directory, args.timeout)
                compare(mode + "/" + case, actual, expected[case])
                completed.append(case)
            report["modes"].append(mode)
            report["runs"][mode] = {"cases": completed, "gc_settings": settings}
            print(f"{mode}: {len(completed)} scenarios match the stdlib oracle", flush=True)
    if hashes() != before:
        raise RuntimeError("prototype sources changed during validation; rerun on the final tree")
    report["result"] = "pass"
    validate_report(report, args.cpython_only)


def write_report(path, report):
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=str(ROOT / "pystachy"),
                        help="native or hosted compiler command, e.g. 'python3 pystachy.py'")
    parser.add_argument("--cc", help="C11 compiler command; defaults to PYSTACHY_LLVM/clang or cc")
    parser.add_argument("--cpython-only", action="store_true", help="stdlib oracle and CPython bridge only")
    parser.add_argument("--repeat", type=int, default=8, help="lifecycles per scenario (default: 8)")
    parser.add_argument("--stress", type=int, default=1, help="native allocation interval for GC-stress modes")
    parser.add_argument("--timeout", type=float, default=60, help="seconds per scenario subprocess")
    parser.add_argument("--build-timeout", type=float, default=180, help="seconds per compiler subprocess")
    parser.add_argument("--json", type=Path, help="atomically replace a verification report, including failures")
    args = parser.parse_args(argv)
    if (args.repeat < 1 or args.stress < 1 or args.timeout <= 0 or args.build_timeout <= 0
            or not math.isfinite(args.timeout) or not math.isfinite(args.build_timeout)):
        parser.error("--repeat, --stress and timeouts must be positive")
    report = {"schema": 1, "result": "running", "cases": [], "modes": [], "runs": {}}
    write_report(args.json, report)
    try:
        check(args, report)
    except Exception as error:
        report.update(result="fail", error=str(error))
        write_report(args.json, report)
        print(str(error), file=sys.stderr)
        return 1
    write_report(args.json, report)
    print("Socket/readiness parity passed for the documented optional prototype surface.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
