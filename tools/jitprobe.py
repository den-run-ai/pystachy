"""Check dead-code removal and inlining at the JIT boundary, without timing thresholds.

usage: python3 tools/jitprobe.py [-c LABEL=COMMAND]...
A transparent lli wrapper inspects the bitcode the driver actually executes: unused functions
never reach it, and a small live helper reaches it inlined into its caller, unless
PYSTACHY_JIT_INLINE=0 turns the JIT's inliner off (#211).
The same boundary checks cover opt-in MCJIT -O0 code generation (#430), including
argv, exception unwinding through runtime callbacks, GC stress and signal status.
"""
import argparse
import os
from pathlib import Path
import re
import signal
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
SOURCE = '''import jitprobe_module
import sys

def note() -> int:
    print("default")
    return 7

def unused_default(x: int = note()) -> int:
    return x

def unused_left(x: int) -> int:
    return unused_right(x - 1) if x else 0

def unused_right(x: int) -> int:
    return unused_left(x - 1) if x else 0

def live_leaf(x: int) -> int:
    return x + 1

def live_root(x: int) -> int:
    return live_leaf(x) * 2

class Item:
    def __init__(self, x: int):
        self.x = x
    def __eq__(self, other: "Item") -> bool:
        return self.x == other.x
    def __lt__(self, other: "Item") -> bool:
        if self.x < 0:
            raise ValueError("callback")
        return self.x < other.x
    def __repr__(self) -> str:
        return f"Item({self.x})"

print(live_root(20))
print([Item(1)] == [Item(1)], [Item(1)] < [Item(2)])
print(sorted([Item(2), Item(1)]))
try:
    sorted([Item(1), Item(-1)])
except ValueError as error:
    print("caught", error)
print(sys.argv)

# Seven fields need 56 bytes on the supported 64-bit targets. LLVM's default
# layout folds their size to 48 before ORC supplies the actual host layout.
class Layout:
    def __init__(self, value: int):
        self.a = True
        self.b = value
        self.c = True
        self.d = value + 1
        self.e = True
        self.f = value + 2
        self.tags: list[str] = []

padded = Layout(17)
padded.tags.append("kept")
print(padded.a, padded.b, padded.c, padded.d, padded.e, padded.f, padded.tags)
'''


def run(command, env):
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=60, check=False)
    if result.returncode or result.stderr:
        raise RuntimeError(f"{shlex.join(command)}: exit {result.returncode}\n{result.stderr.decode()}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", action="append", default=[], metavar="LABEL=COMMAND")
    args = parser.parse_args()
    commands = args.c or [f"hosted={shlex.quote(sys.executable)} -m pystachy", f"native={ROOT / 'pystachy'}"]
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    with tempfile.TemporaryDirectory(prefix="pystachy-jitprobe-") as tmp:
        temp = Path(tmp)
        source = temp / "probe.py"
        source.write_text(SOURCE + "\n".join(f"def unused_{i}(x: int) -> int:\n    return x + {i}\n" for i in range(32)))
        (temp / "jitprobe_module.py").write_text('print("import")\n')
        capture = temp / "executed.ll"
        invocation = temp / "lli-args"
        bindir = temp / "bin"
        bindir.mkdir()
        real = {}
        for name in ("clang", "opt", "lli", "llvm-link", "llvm-as"):
            path = shutil.which(str(Path(llvm) / name) if llvm else name)
            if path is None:
                raise RuntimeError(f"cannot find {name}; set PYSTACHY_LLVM")
            real[name] = str(Path(path).absolute())
            if name != "lli":
                (bindir / name).symlink_to(real[name])
        wrapper = bindir / "lli"
        wrapper.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {shlex.quote(str(invocation))}\n{shlex.quote(real['opt'])} -S -passes=verify /dev/fd/9 -o {shlex.quote(str(capture))} || exit $?\nexec {shlex.quote(real['lli'])} \"$@\"\n")
        wrapper.chmod(0o755)
        env = os.environ | {"PYSTACHY_LLVM": str(bindir), "PYSTACHY_PATH": str(temp)}
        env.pop("PYSTACHY_JIT_INLINE", None)  # (the default's inliner is what is checked first)
        env.pop("PYSTACHY_JIT_CODEGEN", None)
        arguments = ["space here", "'quoted$argument`"]
        expected = run([sys.executable, str(source), *arguments], env)
        for spec in commands:
            label, command = spec.split("=", 1)
            cmd = shlex.split(command)
            raw = run(cmd + ["ir", str(source)], env).decode()
            dead = set(re.findall(r"^define internal .*?@([^ (]*unused_[^ (]*)\(", raw, re.MULTILINE))
            if len(dead) != 35:
                raise RuntimeError(f"{label}: expected 35 emitted unused functions, got {len(dead)}")
            capture.unlink(missing_ok=True)
            if run(cmd + ["run", str(source), *arguments], env) != expected:
                raise RuntimeError(f"{label}: JIT output differs from CPython")
            if any(arg.startswith("-jit-kind=") or arg == "-O0" for arg in invocation.read_text().splitlines()):
                raise RuntimeError(f"{label}: default code generation no longer uses ORC")
            executed = capture.read_text()
            if 'target datalayout = ' not in executed or 'target triple = ' not in executed:
                raise RuntimeError(f"{label}: JIT optimization ran without the runtime's target")
            if not re.search(r"call ptr @pys_alloc\(i64 56\)", executed):
                raise RuntimeError(f"{label}: padded object allocation does not use the host's 56-byte layout")
            remaining = {name for name in dead if f"@{name}(" in executed}
            if remaining:
                raise RuntimeError(f"{label}: {len(remaining)} unused functions reached lli: {sorted(remaining)[:3]}")
            for name in ("pys_obj_eq", "pys_obj_cmp", "pys_obj_repr"):
                if not re.search(rf"^define .*?@{name}\(", executed, re.MULTILINE):
                    raise RuntimeError(f"{label}: runtime callback {name} is missing")
            if re.search(r"call .*@f\.live_leaf\(", executed):
                raise RuntimeError(f"{label}: live_leaf() reached lli as a call, not inlined")
            capture.unlink(missing_ok=True)
            if run(cmd + ["run", str(source), *arguments], env | {"PYSTACHY_JIT_INLINE": "0"}) != expected:
                raise RuntimeError(f"{label}: JIT output without the inliner differs from CPython")
            if not re.search(r"call .*@f\.live_leaf\(", capture.read_text()):
                raise RuntimeError(f"{label}: PYSTACHY_JIT_INLINE=0 inlined live_leaf() all the same")
            print(f"{label}: 35 unused functions removed; live calls, defaults, imports and runtime callbacks preserved; live_leaf() inlined, and not with PYSTACHY_JIT_INLINE=0")
            for mode in ("2", "0"):
                selected = env | {"PYSTACHY_JIT_CODEGEN": mode, "PYSTACHY_GC_STRESS_PROGRAM": "1"}
                if run(cmd + ["run", str(source), *arguments], selected) != expected:
                    raise RuntimeError(f"{label}: codegen={mode} output/argv/callback exception differs")
                flags = invocation.read_text().splitlines()
                if ("-jit-kind=mcjit" in flags) != (mode == "0") or ("-O0" in flags) != (mode == "0"):
                    raise RuntimeError(f"{label}: codegen={mode} selected unexpected lli flags: {flags}")
                signal_case = subprocess.run(cmd + ["run", str(ROOT / "tests/programs/language/exec_signal.py")], cwd=ROOT,
                                             env=selected, capture_output=True, timeout=60, check=False)
                if signal_case.returncode != -signal.SIGTERM or not signal_case.stdout.endswith(b"out\n") or signal_case.stderr != b"last\n":
                    raise RuntimeError(f"{label}: codegen={mode} changed signal status/output: {signal_case}")
            for invalid in ("", "1", "-O0", "0;false"):
                invocation.unlink(missing_ok=True)
                rejected = subprocess.run(cmd + ["run", str(source)], cwd=ROOT,
                                          env=env | {"PYSTACHY_JIT_CODEGEN": invalid}, capture_output=True,
                                          timeout=60, check=False)
                if rejected.returncode == 0 or rejected.stdout or b"PYSTACHY_JIT_CODEGEN:" not in rejected.stderr or invocation.exists():
                    raise RuntimeError(f"{label}: invalid codegen={invalid!r} was not rejected before lli")
            print(f"{label}: default ORC and opt-in MCJIT -O0 preserve argv, callback exceptions, GC stress and SIGTERM; invalid modes rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
