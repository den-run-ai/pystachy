#!/usr/bin/env python3
"""Check inherited descriptors, runtime variants, cleanup and native cache launches."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '''import os
import sys
for argument in sys.argv[1:]:
    descriptor = int(argument)
    if descriptor == 0:
        try:
            with open("/dev/fd/0", "rb") as stream:
                print("stdin unexpectedly open")
        except OSError:
            print("stdin closed")
    else:
        with open("/dev/fd/" + argument, "rb") as stream:
            print(argument, stream.read(len("pipe-" + argument) + 1).hex())
'''
EMBED = '''from pyobj import of_int
number = of_int(42)
print("embedded", number.to_int())
number.close()
'''
BOOTSTRAP = '''import os
import sys
fds = [int(value) for value in sys.argv[1].split(",")]
for target in fds:
    if target == 0:
        os.close(0)
    else:
        reader, writer = os.pipe()
        os.write(writer, ("pipe-" + str(target)).encode())
        os.close(writer)
        os.dup2(reader, target, inheritable=True)
        os.set_inheritable(target, True)
        if reader != target:
            os.close(reader)
os.execvp(sys.argv[2], sys.argv[2:])
'''

EXEC_FAILURE = r'''import builtins
import os
import re
import sys
sys.path.insert(0, sys.argv[1])
from src.pystachy_compiler import driver

inputs = []
reservations = []
real_open = builtins.open
def track_open(path, *args, **kwargs):
    if str(path) != os.devnull and args and args[0] == "rb":
        assert not any(not stream.closed for stream in reservations), "reserved open standard descriptors"
    stream = real_open(path, *args, **kwargs)
    if str(path) == os.devnull:
        reservations.append(stream)
    return stream
builtins.open = track_open

def fail_exec(path, arguments):
    assert path == "/bin/sh", path
    inputs.extend(int(value) for value in re.findall(r"/dev/fd/(\d+)", arguments[2]))
    assert len(inputs) >= 2 and len(inputs) == len(set(inputs)), inputs
    for descriptor in inputs:
        assert descriptor >= 3 and os.get_inheritable(descriptor), descriptor
    raise OSError("injected exec failure")

os.execv = fail_exec
sys.argv = ["pystachy", "run", sys.argv[2]]
try:
    driver.main()
except OSError as error:
    assert str(error) == "injected exec failure", error
else:
    raise AssertionError("exec failure did not propagate")
for descriptor in inputs:
    try:
        os.fstat(descriptor)
    except OSError:
        pass
    else:
        raise AssertionError("launch descriptor leaked: " + str(descriptor))
print("failed exec closed inputs")
'''


def run(command, environment, *, stderr=False):
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=120)
    if result.returncode or (result.stderr and not stderr):
        raise RuntimeError(f"{shlex.join(command)}: exit {result.returncode}\n{result.stderr.decode()}")
    return result


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
        temp = work / "tmp"
        temp.mkdir()
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("PYSTACHY_") and key not in {"PYTHONPATH", "PYTHONHOME"}}
        environment.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_PROGRAM_CACHE="0", TMPDIR=str(temp))
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
                    expected = run([sys.executable, str(launch), ",".join(arguments),
                                    sys.executable, str(program), *arguments], env).stdout
                    for warm in range(2):
                        result = run([sys.executable, str(launch), ",".join(arguments),
                                      *compiler, "run", str(program), *arguments], env)
                        if result.stdout != expected:
                            raise AssertionError(f"{label}/{kind}/{program.stem}/{warm}: {result.stdout!r} != {expected!r}")
                        inputs = trace.read_text().splitlines()
                        runtime = "-dlopen=/dev/fd/" if kind == "shared" else "-extra-object=/dev/fd/"
                        if not any(value.startswith(runtime) for value in inputs):
                            raise AssertionError(f"runtime variant not exercised: {inputs}")
                        if any(temp.iterdir()):
                            raise AssertionError(f"temporary artifacts remain: {list(temp.iterdir())}")
                        checks += 1
            env = environment | {"PYSTACHY_LLVM": str(work / "shared"), "PYSTACHY_CACHE": str(work / (label + "-shared"))}
            for descriptors, stress in [(list(range(3, 40)) + [64], ""), ([0, 7, 8, 9], ""),
                                        ([7, 8, 9], "1"), ([7, 8, 9], "7")]:
                arguments = [str(value) for value in descriptors]
                expected = run([sys.executable, str(launch), ",".join(arguments),
                                sys.executable, str(source), *arguments], env).stdout
                result = run([sys.executable, str(launch), ",".join(arguments),
                              *compiler, "run", str(source), *arguments], env | {"PYSTACHY_GC_STRESS_PROGRAM": stress})
                if result.stdout != expected:
                    raise AssertionError(f"{label}/dense-or-stress: {result.stdout!r} != {expected!r}")
                checks += 1
            if len(compiler) == 1 and Path(compiler[0]).is_file():
                env = environment | {"PYSTACHY_LLVM": str(Path(real["clang"]).parent),
                                     "PYSTACHY_CACHE": str(work / (label + "-program")),
                                     "PYSTACHY_PROGRAM_CACHE": "1", "PYSTACHY_PROGRAM_CACHE_TRACE": "1"}
                arguments = ["7", "8", "9", "64"]
                expected = run([sys.executable, str(launch), ",".join(arguments),
                                sys.executable, str(source), *arguments], env).stdout
                for state in (b"stored", b"hit"):
                    result = run([sys.executable, str(launch), ",".join(arguments),
                                  *compiler, "run", str(source), *arguments], env, stderr=True)
                    if result.stdout != expected or b"pystachy program cache: " + state not in result.stderr:
                        raise AssertionError(f"{label}/cache-{state!r}: {result.stdout!r}, {result.stderr!r}")
                    checks += 1
            print(f"{label}: inherited pipes, closed stdin, shared/object runtimes, embedding, cleanup and GC passed")
        failure = work / "failed-exec.py"
        failure.write_text(EXEC_FAILURE)
        env = environment | {"PYSTACHY_LLVM": str(work / "shared"), "PYSTACHY_CACHE": str(work / (commands[0].split("=", 1)[0] + "-shared"))}
        result = run([sys.executable, str(failure), str(ROOT), str(source)], env)
        if result.stdout != b"failed exec closed inputs\n" or any(temp.iterdir()):
            raise AssertionError(f"failed exec cleanup: {result.stdout!r}, {list(temp.iterdir())}")
        checks += 1
        print(f"jitfdprobe: {checks} checks passed")


if __name__ == "__main__":
    main()
