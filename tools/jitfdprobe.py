#!/usr/bin/env python3
"""Check JIT launches against CPython: inherited descriptors and SIGINT dispositions,
closed standard streams, runtime variants, MCJIT, cleanup and native cache launches."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import sysconfig
import tempfile
import time

from program_cache_probe import TOOL_ENV

ROOT = Path(__file__).resolve().parents[1]
# Reads the inherited descriptors it is given, then lists its whole descriptor table, so that
# a descriptor CPython does not have fails the comparison, and runs a child (JITFD_CHILD) that
# lists what it inherited. JITFD_REPORT receives the report where standard streams are closed.
SOURCE = '''import os
import sys
lines = []
for argument in sys.argv[1:]:
    descriptor = int(argument)
    if descriptor < 3:
        try:
            with open("/dev/fd/" + argument, "rb") as stream:
                lines.append(argument + " unexpectedly open")
        except OSError:
            lines.append(argument + " closed")
    else:
        with open("/dev/fd/" + argument, "rb") as stream:
            lines.append(argument + " " + stream.read(len("pipe-" + argument) + 1).hex())
for fd in sorted([int(name) for name in os.listdir("/proc/self/fd")]):
    lines.append("fd " + str(fd) + " " + os.path.realpath("/proc/self/fd/" + str(fd)))
report = os.getenv("JITFD_REPORT", "")
if report == "":
    print("\\n".join(lines))
    sys.stdout.flush()
else:
    with open(report, "w") as output:
        output.write("\\n".join(lines) + "\\n")
child = os.getenv("JITFD_CHILD", "")
if child != "":
    os.system(child)
'''
EMBED = '''from pyobj import of_int
number = of_int(42)
print("embedded", number.to_int())
number.close()
'''
# Waits for the end of its input after reporting a child's view; the probe sends SIGINT first.
SIGNAL_SOURCE = '''import os
import sys
child = os.getenv("JITFD_CHILD", "")
if child != "":
    os.system(child)
print("ready", flush=True)
data = sys.stdin.read()
print("survived", len(data))
'''
# What a program's child inherits: its descriptors, SIGINT disposition and launch variables.
CHILD = '''import os
import signal
import sys
fds = sorted(int(name) for name in os.listdir("/proc/self/fd"))
sigint = "ignored" if signal.getsignal(signal.SIGINT) == signal.SIG_IGN else "not ignored"
line = (f"child fds {fds} SIGINT {sigint} PYSTACHY_JIT_HANDOFF {'PYSTACHY_JIT_HANDOFF' in os.environ}"
        f" JITDUMPDIR {'JITDUMPDIR' in os.environ}\\n")
if len(sys.argv) > 1:
    with open(sys.argv[1], "a") as stream:
        stream.write(line)
else:
    sys.stdout.write(line)
'''
# Closes the standard streams it is given and puts pipes on the other descriptors, sets SIGINT's
# disposition (JITFD_SIGINT: ignore, default, or a handler that exec resets), then execs.
BOOTSTRAP = '''import os
import signal
import sys
fds = [int(value) for value in sys.argv[1].split(",") if value]
for target in fds:
    if target < 3:
        os.close(target)
    else:
        reader, writer = os.pipe()
        os.write(writer, ("pipe-" + str(target)).encode())
        os.close(writer)
        os.dup2(reader, target, inheritable=True)
        os.set_inheritable(target, True)
        if reader != target:
            os.close(reader)
disposition = os.environ.pop("JITFD_SIGINT", "")
if disposition:
    signal.signal(signal.SIGINT, {"ignore": signal.SIG_IGN, "default": signal.SIG_DFL,
                                  "handler": lambda number, frame: None}[disposition])
os.execvp(sys.argv[2], sys.argv[2:])
'''

EXEC_FAILURE = r'''import builtins
import os
import re
import sys
sys.path.insert(0, sys.argv[1])
from src.pystachy_compiler import driver

launched = []
probes = []
real_open = builtins.open
def track_open(path, *args, **kwargs):
    if str(path) != os.devnull and args and args[0] == "rb":
        assert all(stream.closed or stream.fileno() < 3 for stream in probes), "a /dev/null probe keeps a descriptor"
    stream = real_open(path, *args, **kwargs)
    if str(path) == os.devnull:
        probes.append(stream)
    return stream
builtins.open = track_open
closed = [int(value) for value in os.environ["JITFD_CLOSED"].split(",") if value]
mcjit = os.environ.get("PYSTACHY_JIT_CODEGEN") == "0"

def fail_exec(path, arguments):
    assert path == "/bin/sh", path
    script = arguments[2]
    inputs = [int(value) for value in re.findall(r"/dev/fd/(\d+)", script)]
    assert len(inputs) >= 2 and len(inputs) == len(set(inputs)), inputs
    handoff = re.search(r"PYSTACHY_JIT_HANDOFF='(\d+);([\d,]*);([^']*)'", script)
    assert handoff, script
    listed = [int(value) for value in handoff.group(2).split(",")]
    assert listed == closed + [fd for fd in listed if fd >= 3] and sorted(listed[len(closed):]) == sorted(inputs), (listed, inputs)
    for descriptor in listed:
        assert os.get_inheritable(descriptor), descriptor
    for descriptor in closed:
        assert os.path.samefile("/proc/self/fd/" + str(descriptor), os.devnull), descriptor
    ignored = int(handoff.group(1))
    assert ignored == driver.ignored_signals() and (ignored >> 1 & 1) == (os.environ["JITFD_IGNORED"] == "1"), ignored
    dump = handoff.group(3)
    assert (dump != "") == mcjit and (not mcjit or os.path.isdir(dump) and "JITDUMPDIR='" + dump + "'" in script), script
    launched.extend(listed)
    launched.append(dump)
    raise OSError("injected exec failure")

os.execv = fail_exec
sys.argv = ["pystachy", "run", sys.argv[2]]
try:
    driver.main()
except OSError as error:
    assert str(error) == "injected exec failure", error
else:
    raise AssertionError("exec failure did not propagate")
for descriptor in launched[:-1]:
    try:
        os.fstat(descriptor)
    except OSError:
        pass
    else:
        raise AssertionError("launch descriptor leaked: " + str(descriptor))
assert launched[-1] == "" or not os.path.exists(launched[-1]), launched
print("failed exec closed inputs")
'''
# MCJIT's perf jitdump, where LLVM has perf support: lli's own close-on-exec descriptor, which
# lli writes and closes at exit; the runtime removed its file and directory before the program.
JITDUMP = re.compile(rb"(?m)^fd \d+ [^\n]*/\.debug/jit/llvm-IR-jit-[^/\n]*/jit-\d+\.dump \(deleted\)\n")


def run(command, environment, *, stderr=False):
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=120)
    if result.returncode or (result.stderr and not stderr):
        raise RuntimeError(f"{shlex.join(command)}: exit {result.returncode}\n{result.stderr.decode()}")
    return result


def normalized(report, mcjit=False):
    # Process IDs and pipe inodes differ between runs; MCJIT may keep its jitdump descriptor.
    text = re.sub(rb"/proc/\d+/fd/", b"/proc/PID/fd/", report)
    text = re.sub(rb"(pipe|socket):\[\d+\]", rb"\1:[]", text)
    text, dumps = JITDUMP.subn(b"", text) if mcjit else (text, 0)
    if dumps > 1:
        raise AssertionError(f"{dumps} jitdump descriptors: {report!r}")
    return text


def interrupted(command, environment, number=signal.SIGINT, timeout=120):
    """Run COMMAND until it prints ready, send it signal NUMBER, then end its input."""
    process = subprocess.Popen(command, cwd=ROOT, env=environment, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        output = b""
        end = time.monotonic() + timeout
        while b"ready\n" not in output:
            remaining = end - time.monotonic()
            if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                raise AssertionError(f"{shlex.join(command)}: not ready after {timeout} s: {output!r}")
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                process.wait(timeout=timeout)
                raise AssertionError(f"{shlex.join(command)}: exit {process.returncode} before ready: "
                                     f"{output!r}, {process.stderr.read()!r}")
            output += chunk
        # An ignored signal is discarded as it is sent; any other is pending before the input ends.
        os.kill(process.pid, number)
        rest, error = process.communicate(b"", timeout=timeout)
    finally:
        if process.returncode is None:
            process.kill()
            process.wait()
    lines = [line for line in error.splitlines() if not line.startswith(b"pystachy program cache: ")]
    return process.returncode, output + rest, lines[-1] if lines else b"", error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", action="append", default=[], metavar="LABEL=COMMAND")
    args = parser.parse_args()
    commands = args.c or [f"hosted={shlex.quote(sys.executable)} -m pystachy", f"native={ROOT / 'pystachy'}"]
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    if sys.platform != "linux":
        print("jitfdprobe: skipped (Linux descriptor paths and program cache required)")
        return
    with tempfile.TemporaryDirectory(prefix="pystachy-jitfds-") as temporary:
        work = Path(temporary)
        launch = work / "launch.py"
        launch.write_text(BOOTSTRAP)
        source = work / "pipes.py"
        source.write_text(SOURCE)
        embedded = work / "embedded.py"
        embedded.write_text(EMBED + SOURCE)
        waiting = work / "waits.py"
        waiting.write_text(SIGNAL_SOURCE)
        child = work / "child.py"
        child.write_text(CHILD)
        report = work / "report"
        temp = work / "tmp"
        temp.mkdir()
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("PYSTACHY_") and key not in {"PYTHONPATH", "PYTHONHOME", "JITDUMPDIR"}
                       and not key.startswith("JITFD_")}
        environment.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_PROGRAM_CACHE="0", TMPDIR=str(temp),
                           JITFD_CHILD=shlex.join([sys.executable, "-I", str(child)]))
        library = Path(sysconfig.get_config_var("LIBDIR")) / sysconfig.get_config_var("LDLIBRARY")
        environment.update(PYSTACHY_LIBPYTHON=str(library), PYTHONHOME=sys.base_prefix,
                           PYTHONPATH=str(ROOT / "tools" / "rt_cpython"))
        trace = work / "lli-inputs"
        real = {name: shutil.which(str(Path(llvm) / name) if llvm else name)
                for name in ("clang", "opt", "lli", "llvm-link", "llvm-as")}
        if not all(real.values()):
            raise RuntimeError("complete LLVM toolchain required; set PYSTACHY_LLVM")
        for kind in ("shared", "object"):
            directory = work / kind
            directory.mkdir()
            for name, target in real.items():
                if name == "lli":
                    wrapper = directory / name
                    wrapper.write_text(
                        f"#!{sys.executable}\nimport os, sys\n"
                        f"with open({str(trace)!r}, 'w') as output:\n"
                        " for value in sys.argv[1:]:\n"
                        "  path = value.split('=', 1)[-1]\n"
                        "  if path.startswith('/dev/fd/'):\n"
                        "   output.write(value + '\\n')\n"
                        "   target = os.readlink(path)\n"
                        f"   if target.startswith({str(temp)!r}):\n"
                        "    assert target.endswith(' (deleted)'), target\n"
                        "    assert not os.path.exists(os.path.dirname(target)), target\n"
                        f"os.execv({target!r}, [{target!r}, *sys.argv[1:]])\n")
                    wrapper.chmod(0o755)
                elif name == "clang" and kind == "object":
                    wrapper = directory / name
                    wrapper.write_text(f"#!/bin/sh\nfor arg do [ \"$arg\" != -shared ] || exit 1; done\nexec {shlex.quote(target)} \"$@\"\n")
                    wrapper.chmod(0o755)
                else:
                    (directory / name).symlink_to(target)

        def clean(what):
            if any(temp.iterdir()):
                raise AssertionError(f"{what}: temporary artifacts remain: {sorted(temp.rglob('*'))}")

        def compare(what, descriptors, compiler, env, *, mcjit=False):
            # Standard streams that the caller closes are closed in the program and its child too.
            arguments = [str(value) for value in descriptors]
            env = env | ({"PYSTACHY_JIT_CODEGEN": "0"} if mcjit else {})
            closed = any(value < 3 for value in descriptors)
            if closed:
                env = env | {"JITFD_REPORT": str(report), "JITFD_CHILD": env["JITFD_CHILD"] + " " + shlex.quote(str(report))}
            outputs = []
            for command in ([sys.executable], compiler + ["run"]):
                report.unlink(missing_ok=True)
                result = run([sys.executable, str(launch), ",".join(arguments), *command, str(source), *arguments], env)
                outputs.append(normalized(report.read_bytes() if closed else result.stdout, mcjit))
            if outputs[1] != outputs[0]:
                raise AssertionError(f"{what}: {outputs[1]!r} != {outputs[0]!r}")
            clean(what)

        def interrupt(what, disposition, command, env, number=signal.SIGINT):
            # SIGINT ignored by the caller stays ignored, also in the program's child; a default or
            # caught one (exec resets a handler) raises KeyboardInterrupt, as in CPython. Another
            # signal that LLVM handles in lli (SIGUSR1) has its default action, as in CPython.
            env = env | {"JITFD_SIGINT": disposition}
            launched = [sys.executable, str(launch), ""]
            expected = interrupted(launched + [sys.executable, str(waiting)], env, number)[:3]
            result = interrupted(launched + command, env, number)
            what += f"/{disposition}/{signal.Signals(number).name}"
            if result[:3] != expected:
                raise AssertionError(f"{what}: {result} != {expected}")
            if expected[0] != (0 if disposition == "ignore" and number == signal.SIGINT else -number):
                raise AssertionError(f"{what}: CPython's control {expected}")
            clean(what)
            return result

        checks = 0
        for spec in commands:
            label, command = spec.split("=", 1)
            compiler = shlex.split(command)
            for kind in ("shared", "object"):
                env = environment | {"PYSTACHY_LLVM": str(work / kind), "PYSTACHY_CACHE": str(work / (label + "-" + kind))}
                for program in (source, embedded):
                    if program == embedded and not library.is_file():
                        raise RuntimeError("embedding regression requires a shared libpython")
                    descriptors = [7, 8, 9, 64]
                    arguments = [str(value) for value in descriptors]
                    expected = normalized(run([sys.executable, str(launch), ",".join(arguments),
                                               sys.executable, str(program), *arguments], env).stdout)
                    for warm in range(2):
                        result = run([sys.executable, str(launch), ",".join(arguments),
                                      *compiler, "run", str(program), *arguments], env)
                        if normalized(result.stdout) != expected:
                            raise AssertionError(f"{label}/{kind}/{program.stem}/{warm}: {result.stdout!r} != {expected!r}")
                        inputs = trace.read_text().splitlines()
                        runtime = "-dlopen=/dev/fd/" if kind == "shared" else "-extra-object=/dev/fd/"
                        if not any(value.startswith(runtime) for value in inputs):
                            raise AssertionError(f"runtime variant not exercised: {inputs}")
                        clean(f"{label}/{kind}/{program.stem}/{warm}")
                        checks += 1
            # (the shared runtime's SIGINT cases follow; the object runtime's restores it the same way)
            env = environment | {"PYSTACHY_LLVM": str(work / "object"), "PYSTACHY_CACHE": str(work / (label + "-object"))}
            interrupt(f"{label}/object", "ignore", compiler + ["run", str(waiting)], env)
            checks += 1
            env = environment | {"PYSTACHY_LLVM": str(work / "shared"), "PYSTACHY_CACHE": str(work / (label + "-shared"))}
            for descriptors, stress in [(list(range(3, 40)) + [64], ""), ([0, 7, 8, 9], ""),
                                        ([7, 8, 9], "1"), ([7, 8, 9], "7")]:
                compare(f"{label}/dense-or-stress", descriptors, compiler, env | {"PYSTACHY_GC_STRESS_PROGRAM": stress})
                checks += 1
            for descriptors, mcjit in [([1, 2, 7, 8, 9], False), ([0, 1, 2, 7, 8, 9], True)]:
                compare(f"{label}/closed-mcjit-{mcjit}", descriptors, compiler, env, mcjit=mcjit)
                checks += 1
            for disposition, codegen, number in [("ignore", "2", signal.SIGINT), ("default", "2", signal.SIGINT),
                                                 ("handler", "2", signal.SIGINT), ("ignore", "2", signal.SIGINT),
                                                 ("ignore", "0", signal.SIGINT), ("default", "0", signal.SIGINT),
                                                 ("ignore", "2", signal.SIGUSR1), ("ignore", "0", signal.SIGUSR1)]:
                interrupt(f"{label}/codegen-{codegen}", disposition, compiler + ["run", str(waiting)],
                          env | {"PYSTACHY_JIT_CODEGEN": codegen}, number)
                checks += 1
            if len(compiler) == 1 and Path(compiler[0]).is_file():
                # Build overrides deliberately bypass the program cache; setup-python
                # supplies LD_LIBRARY_PATH in CI. Keep this control eligible, as in
                # the dedicated program-cache probe, without changing driver policy.
                cache_environment = {key: value for key, value in environment.items()
                                     if key not in TOOL_ENV}
                env = cache_environment | {"PYSTACHY_LLVM": str(Path(real["clang"]).parent),
                                           "PYSTACHY_CACHE": str(work / (label + "-program")),
                                           "PYSTACHY_PROGRAM_CACHE": "1", "PYSTACHY_PROGRAM_CACHE_TRACE": "1"}
                arguments = ["7", "8", "9", "64"]
                expected = normalized(run([sys.executable, str(launch), ",".join(arguments),
                                           sys.executable, str(source), *arguments], env).stdout)
                for state in (b"stored", b"hit"):
                    result = run([sys.executable, str(launch), ",".join(arguments),
                                  *compiler, "run", str(source), *arguments], env, stderr=True)
                    if normalized(result.stdout) != expected or b"pystachy program cache: " + state not in result.stderr:
                        raise AssertionError(f"{label}/cache-{state!r}: {result.stdout!r}, {result.stderr!r}")
                    checks += 1
                for state in (b"stored", b"hit"):
                    result = interrupt(f"{label}/cache-{state.decode()}", "ignore", compiler + ["run", str(waiting)], env)
                    if b"pystachy program cache: " + state not in result[3]:
                        raise AssertionError(f"{label}/cache-{state!r}: {result[3]!r}")
                    checks += 1
                executable = work / (label + "-waits")
                run([*compiler, "build", str(waiting), "-o", str(executable)], env, stderr=True)
                for disposition in ("ignore", "default", "handler"):
                    interrupt(f"{label}/aot", disposition, [str(executable)], env)
                    checks += 1
            print(f"{label}: inherited pipes and descriptor tables, closed standard streams, SIGINT dispositions,"
                  " shared/object runtimes, MCJIT, embedding, cleanup and GC passed")
        failure = work / "failed-exec.py"
        failure.write_text(EXEC_FAILURE)
        env = environment | {"PYSTACHY_LLVM": str(work / "shared"), "PYSTACHY_CACHE": str(work / (commands[0].split("=", 1)[0] + "-shared"))}
        for closed, codegen, disposition in [("", "2", "default"), ("0", "0", "ignore")]:
            result = run([sys.executable, str(launch), closed, sys.executable, str(failure), str(ROOT), str(source)],
                         env | {"JITFD_CLOSED": closed, "PYSTACHY_JIT_CODEGEN": codegen, "JITFD_SIGINT": disposition,
                                "JITFD_IGNORED": "1" if disposition == "ignore" else "0"})
            if result.stdout != b"failed exec closed inputs\n":
                raise AssertionError(f"failed exec cleanup: {result.stdout!r}")
            clean("failed exec")
            checks += 1
        print(f"jitfdprobe: {checks} checks passed")


if __name__ == "__main__":
    main()
