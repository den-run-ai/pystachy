"""Check dead-code removal and inlining at the JIT boundary, without timing thresholds.

usage: python3 tools/jitprobe.py [-c LABEL=COMMAND]...
Transparent wrappers around the JIT runner (lljit.c, which the driver builds in this probe's own
cache, then wrapped) and lli inspect the bitcode the driver actually executes: unused functions
never reach it, and a small live helper reaches it inlined into its caller, unless
PYSTACHY_JIT_INLINE=0 turns the JIT's inliner off (#211).
Unused loop feedback must also disappear after SSA promotion, while live loop results
and side effects remain. The same boundary checks cover both runners (the default, and lli with
PYSTACHY_JIT_LAUNCHER=lli) in both levels of code generation (#430): the runner generates code at
the -O it is given, and for -O0 lli's ORC links an object of llc's beside a main module that holds
only the runtime callbacks' constructor. Each covers argv, exception unwinding, values that a loop
passes to an except clause (critical edges split for -O0), coroutine lowering, GC stress, signal
status and the PYSTACHY_TIMING record that names the runner. The runtime's small functions that a
loop calls (a list[float]'s reads and assignments, float division, math.sqrt(), shifts and int %)
reach the module the runner executes inlined (jit_helpers, #705), with no copy left of them, and as
calls with PYSTACHY_OPT=-jithelpers, both as CPython prints, under GC stress too.
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

def loop_feedback(n: int) -> int:
    dead = 17
    total = 0
    for i in range(n):
        if i & 1:
            dead = dead ^ i
        total += i
    print("feedback", n)
    return total

print(loop_feedback(7))

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


COROUTINE_SOURCE = """from typing import Iterator

def numbers(n: int) -> Iterator[int]:
    try:
        for i in range(n):
            yield i
    finally:
        print("closed")

print(list(numbers(4)))
"""


# a loop of the runtime's small functions, and their errors (#705)
HELPERS_SOURCE = """import math
import sys

def kernel(xs: list[float], ys: list[float], n: int, k: int) -> float:
    s = 0.0
    for i in range(n):
        j = (i * 7 + k) % n
        d = xs[i] - ys[j]
        s += math.sqrt(d * d + 1.0) / (2.0 + xs[j])
        ys[j] = xs[i] * 0.5
        s += float((i << 3) >> 2)
    return s

xs = [float(i % 13) for i in range(100)]
ys = [float(i % 7) for i in range(100)]
print(kernel(xs, ys, 100, len(sys.argv)))
for case in range(3):
    try:
        if case == 0:
            print(kernel(xs[:10], ys, 100, 1))
        elif case == 1:
            xs[3] = -2.0
            print(kernel(xs, ys, 100, 1))
        else:
            print(math.sqrt(xs[3]))
    except (IndexError, ZeroDivisionError, ValueError) as error:
        print(type(error).__name__, error)
"""
HELPERS = ["pys_list_get", "pys_list_set", "pys_m_sqrt", "pys_fdiv", "pys_shl", "pys_shr", "pys_mod"]


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
        coroutine = temp / "coroutine.py"
        coroutine.write_text(COROUTINE_SOURCE)
        helpers = temp / "helpers.py"
        helpers.write_text(HELPERS_SOURCE)
        (temp / "jitprobe_module.py").write_text('print("import")\n')
        capture = temp / "executed.ll"
        invocation = temp / "lli-args"
        compiled = temp / "compiled.ll"
        codegen = temp / "llc-args"
        bindir = temp / "bin"  # (lli: the JIT runner cannot be built for a script, which lli is here)
        bindir.mkdir()
        runnerdir = temp / "runner"  # (the real lli, whose libLLVM the runner links; llc never runs)
        runnerdir.mkdir()
        real = {}
        for name in ("clang", "opt", "lli", "llvm-link", "llvm-as", "llc"):
            path = shutil.which(str(Path(llvm) / name) if llvm else name)
            if path is None:
                raise RuntimeError(f"cannot find {name}; set PYSTACHY_LLVM")
            real[name] = str(Path(path).absolute())
            if name not in ("lli", "llc"):
                (bindir / name).symlink_to(real[name])
            if name != "llc":
                (runnerdir / name).symlink_to(real[name])
        # lli's or the runner's main module (its first bare /dev/fd input), and the bitcode that llc
        # compiles for it
        capturing = (f"printf '%s\\n' \"$@\" > {shlex.quote(str(invocation))}\nfor arg do\n  case $arg in /dev/fd/*) input=$arg; break;; esac\ndone\n"
                     f"{shlex.quote(real['opt'])} -S -passes=verify \"$input\" -o {shlex.quote(str(capture))} || exit $?\n")
        wrapper = bindir / "lli"
        wrapper.write_text(f"#!/bin/sh\n{capturing}exec {shlex.quote(real['lli'])} \"$@\"\n")
        wrapper.chmod(0o755)
        for directory in (bindir, runnerdir):
            wrapper = directory / "llc"
            wrapper.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {shlex.quote(str(codegen))}\nout=\nfor arg do\n  if [ -n \"$out\" ]; then out=; continue; fi\n  case $arg in -o) out=1;; -*) ;; *) input=$arg;; esac\ndone\n{shlex.quote(real['opt'])} -S -passes=verify \"$input\" -o {shlex.quote(str(compiled))} || exit $?\nexec {shlex.quote(real['llc'])} \"$@\"\n")
            wrapper.chmod(0o755)
        # Native program caching skips the lli wrapper even when filling an entry. The runner is
        # built in this probe's runtime cache, then wrapped (wrap_runner)
        cache = temp / "cache"
        cache.mkdir()
        # (seeded with the runtimes of the caller's cache, built from the same files: where the caller's
        # runs warmed it, as verify's contracts do, none is built again here)
        caller = Path(os.environ.get("PYSTACHY_CACHE") or ROOT / "build")
        if caller.is_dir():
            for entry in [*caller.glob("runtime-py-*"), caller / "runtime-py.hashes"]:
                try:
                    shutil.copy2(entry, cache / entry.name)
                except OSError:
                    pass  # (an entry being replaced, or none: built here)
        env = os.environ | {"PYSTACHY_PATH": str(temp), "PYSTACHY_PROGRAM_CACHE": "0", "PYSTACHY_CACHE": str(cache)}
        env.pop("PYSTACHY_JIT_INLINE", None)  # (the default's inliner is what is checked first)
        env.pop("PYSTACHY_JIT_CODEGEN", None)
        env.pop("PYSTACHY_OPT", None)
        env.pop("PYSTACHY_TIMING", None)
        runners = {"lljit": env | {"PYSTACHY_LLVM": str(runnerdir), "PYSTACHY_JIT_LAUNCHER": "auto"},
                   "lli": env | {"PYSTACHY_LLVM": str(bindir), "PYSTACHY_JIT_LAUNCHER": "lli"}}
        arguments = ["space here", "'quoted$argument`"]
        expected = run([sys.executable, str(source), *arguments], env)
        coroutine_expected = run([sys.executable, str(coroutine)], env)
        helpers_expected = run([sys.executable, str(helpers)], env)
        handler = ROOT / "tests/programs/exceptions/exc_handler_loop_values.py"
        handler_expected = run([sys.executable, str(handler)], env)

        def wrap_runner():
            # the runner that the driver built and cached, replaced with a wrapper that captures what
            # it is given, then runs it (the driver keys the cache by its inputs, not by this file)
            built = [entry for entry in cache.iterdir() if re.fullmatch(r"lljit-[0-9a-f]{8}-[0-9a-f]{16}", entry.name)]
            if len(built) != 1:
                raise RuntimeError(f"the JIT runner was not built once in the probe's cache: {sorted(entry.name for entry in cache.iterdir())}")
            if built[0].read_bytes().startswith(b"#!"):
                return
            original = temp / "lljit"
            shutil.move(str(built[0]), original)
            built[0].write_text(f"#!/bin/sh\n{capturing}exec {shlex.quote(str(original))} \"$@\"\n")
            built[0].chmod(0o755)

        for spec in commands:
            label, command = spec.split("=", 1)
            cmd = shlex.split(command)
            raw = run(cmd + ["ir", str(source)], env).decode()
            # (unused_left and unused_right recur only through each other: closed recursion emits each
            # as its symbol and a body, @r.<symbol> (docs/internals.md#native-recursion-depth), and
            # neither may reach lli)
            dead = set(re.findall(r"^define internal .*?@([^ (]*unused_[^ (]*)\(", raw, re.MULTILINE))
            unused = {name.removeprefix("r.") for name in dead}
            feedback = re.search(r"^define[^\n]*@f\.loop_feedback\([^\n]*\n.*?^}", raw, re.MULTILINE | re.DOTALL)
            if feedback is None or "xor i64" not in feedback.group():
                raise RuntimeError(f"{label}: loop-feedback probe did not emit its dead xor")
            if len(unused) != 35 or len(dead) != 37:
                raise RuntimeError(f"{label}: expected 35 emitted unused functions in 37 definitions, got {len(unused)} in {len(dead)}")
            for name, chosen in runners.items():
                where = f"{label}/{name}"
                runner = name == "lljit"
                capture.unlink(missing_ok=True)
                codegen.unlink(missing_ok=True)
                invocation.unlink(missing_ok=True)
                # (the first run of the runner builds it in the probe's cache: wrapped once built)
                if runner and run(cmd + ["run", str(source), *arguments], chosen) != expected:
                    raise RuntimeError(f"{where}: JIT output differs from CPython")
                if runner:
                    wrap_runner()
                if run(cmd + ["run", str(source), *arguments], chosen) != expected:
                    raise RuntimeError(f"{where}: JIT output differs from CPython")
                flags = invocation.read_text().splitlines()
                # (the runner generates code at the -O it is given, -O2 by default; lli takes none)
                if any(arg.startswith("-jit-kind=") for arg in flags) or codegen.exists() or \
                        [arg for arg in flags if re.fullmatch(r"-O[0-3]", arg)] != (["-O2"] if runner else []):
                    raise RuntimeError(f"{where}: default code generation no longer uses ORC alone at -O2: {flags}")
                executed = capture.read_text()
                if 'target datalayout = ' not in executed or 'target triple = ' not in executed:
                    raise RuntimeError(f"{where}: JIT optimization ran without the runtime's target")
                # (the object's allocation: pys_alloc's in the frontend's IR, since the object holds a
                # list: only an object that holds no reference may come from pys_new's marked call,
                # which LLVM may delete, lowering's alloc_call. The JIT tier inlines the fast path of
                # both, lower_module.py's JITFAST, whose slow path calls pys_gc_slow with the size and 0,
                # scanned memory: there the size is the host's 56-byte layout)
                if not re.search(r"call ptr @pys_alloc\(i64 ptrtoint \(ptr getelementptr \(%C\.Layout, ptr null, i32 1\) to i64\)\)", raw):
                    raise RuntimeError(f"{where}: padded object allocation does not use pys_alloc")
                if not re.search(r"call ptr @pys_gc_slow\(i64 56, i64 0\)", executed):
                    raise RuntimeError(f"{where}: padded object allocation does not reach the fast path's slow call with the host's 56-byte layout")
                remaining = {name for name in dead if f"@{name}(" in executed}
                if remaining:
                    raise RuntimeError(f"{where}: {len(remaining)} unused functions reached the JIT: {sorted(remaining)[:3]}")
                for callback in ("pys_obj_eq", "pys_obj_cmp", "pys_obj_repr"):
                    if not re.search(rf"^define .*?@{callback}\(", executed, re.MULTILINE):
                        raise RuntimeError(f"{where}: runtime callback {callback} is missing")
                if re.search(r"call .*@f\.live_leaf\(", executed):
                    raise RuntimeError(f"{where}: live_leaf() reached the JIT as a call, not inlined")
                capture.unlink(missing_ok=True)
                if run(cmd + ["run", str(source), *arguments], chosen | {"PYSTACHY_JIT_INLINE": "0"}) != expected:
                    raise RuntimeError(f"{where}: JIT output without the inliner differs from CPython")
                if not re.search(r"call .*@f\.live_leaf\(", capture.read_text()):
                    raise RuntimeError(f"{where}: PYSTACHY_JIT_INLINE=0 inlined live_leaf() all the same")
                feedback = re.search(r"^define[^\n]*@f\.loop_feedback\([^\n]*\n.*?^}", capture.read_text(), re.MULTILINE | re.DOTALL)
                if feedback is None or "xor i64" in feedback.group() or "%dead." in feedback.group():
                    raise RuntimeError(f"{where}: unused loop feedback reached the JIT")
                if run(cmd + ["run", str(coroutine)], chosen) != coroutine_expected:
                    raise RuntimeError(f"{where}: coroutine output/finally differs from CPython")
                if re.search(r"\b(?:call|invoke)\b[^\n]*@llvm\.coro\.", capture.read_text()):
                    raise RuntimeError(f"{where}: unlowered coroutine operation reached the JIT")
                # (what runs the program, which PYSTACHY_TIMING names: nothing else reaches stderr)
                timed = subprocess.run(cmd + ["run", str(coroutine)], cwd=ROOT, env=chosen | {"PYSTACHY_TIMING": "1"},
                                       capture_output=True, timeout=60, check=False)
                records = [line.split("\t")[1] for line in timed.stderr.decode().splitlines() if line.startswith("pystachy-timing\t")]
                want = "program.jit_runner.lljit" if runner else "program.jit_runner.lli.forced"
                if timed.returncode or timed.stdout != coroutine_expected or want not in records or \
                        len(records) != len(timed.stderr.decode().splitlines()) or \
                        runner != ("program.jit_codegen" in records[records.index(want):]):
                    raise RuntimeError(f"{where}: PYSTACHY_TIMING does not name {want} alone: {timed}")
                print(f"{where}: 35 unused functions removed; live calls, defaults, imports and runtime callbacks preserved; live_leaf() inlined, and not with PYSTACHY_JIT_INLINE=0; unused loop feedback removed")
                for mode in ("2", "0"):
                    selected = chosen | {"PYSTACHY_JIT_CODEGEN": mode, "PYSTACHY_GC_STRESS_PROGRAM": "1"}
                    codegen.unlink(missing_ok=True)
                    if run(cmd + ["run", str(source), *arguments], selected) != expected:
                        raise RuntimeError(f"{where}: codegen={mode} output/argv/callback exception differs")
                    if run(cmd + ["run", str(coroutine)], selected) != coroutine_expected:
                        raise RuntimeError(f"{where}: codegen={mode} coroutine output/finally differs under GC stress")
                    # (-O0 with lli: llc compiles the cleaned-up module, and lli links that object beside a
                    # main module of the program's target that defines no function but the callbacks'
                    # constructor; the runner generates the code itself, at -O0)
                    program = (compiled if mode == "0" and not runner else capture).read_text()
                    if re.search(r"\b(?:call|invoke)\b[^\n]*@llvm\.coro\.", program):
                        raise RuntimeError(f"{where}: codegen={mode} unlowered coroutine operation reached code generation")
                    flags = invocation.read_text().splitlines()
                    shared = any(arg.startswith("-dlopen=/dev/fd/") for arg in flags)
                    objects = len([arg for arg in flags if arg.startswith("-extra-object=/dev/fd/")])
                    levels = [arg for arg in flags if re.fullmatch(r"-O[0-3]", arg)]
                    if any(arg.startswith("-jit-kind=") for arg in flags) or levels != ([f"-O{mode}"] if runner else []) or \
                            objects != (not shared) + (mode == "0" and not runner) or "-profile-guided-section-prefix=false" not in flags:
                        raise RuntimeError(f"{where}: codegen={mode} selected unexpected flags: {flags}")
                    if (mode == "2" or runner) and codegen.exists():
                        raise RuntimeError(f"{where}: codegen={mode} ran llc")
                    if mode == "0" and not runner:
                        llc = codegen.read_text().splitlines()
                        if any(arg not in llc for arg in ("-O0", "-filetype=obj", "-relocation-model=pic",
                                                          "-profile-guided-section-prefix=false")) or \
                                any(arg.startswith(("-mcpu", "-mattr", "-march")) for arg in llc):
                            raise RuntimeError(f"{where}: codegen=0 selected unexpected llc flags: {llc}")
                        main = capture.read_text()
                        defined = re.findall(r"^define [^@]*@([^(]*)\(", main, re.MULTILINE)
                        if 'target datalayout = ' not in main or 'target triple = ' not in main or \
                                defined != (["pys.obj.hooks"] if shared else []) or \
                                not re.search(r"^define [^\n]*@pys_obj_repr\(", program, re.MULTILINE):
                            raise RuntimeError(f"{where}: codegen=0 main module or object differs: {defined}")
                    if mode == "0" and runner and (not re.search(r"^define [^\n]*@pys_obj_repr\(", program, re.MULTILINE) or
                                                   bool(re.search(r"^define [^\n]*@pys\.obj\.hooks\(", program, re.MULTILINE)) != shared):
                        raise RuntimeError(f"{where}: codegen=0 module differs: callbacks or their constructor")
                    # (values a loop passes to an except clause: -O0 PHI elimination needs the critical
                    # edges that the driver splits before code generation, docs/internals.md)
                    if run(cmd + ["run", str(handler)], selected) != handler_expected:
                        raise RuntimeError(f"{where}: codegen={mode} values reaching an except clause differ")
                    if mode == "0" and "_crit_edge" not in (capture if runner else compiled).read_text():
                        raise RuntimeError(f"{where}: codegen=0 reached code generation without split critical edges")
                    signal_case = subprocess.run(cmd + ["run", str(ROOT / "tests/programs/language/exec_signal.py")], cwd=ROOT,
                                                 env=selected, capture_output=True, timeout=60, check=False)
                    if signal_case.returncode != -signal.SIGTERM or not signal_case.stdout.endswith(b"out\n") or signal_case.stderr != b"last\n":
                        raise RuntimeError(f"{where}: codegen={mode} changed signal status/output: {signal_case}")
                print(f"{where}: default and -O0 code generation ({'the runner' if runner else 'ORC, and llc objects'}) preserve argv, callback exceptions, except-clause values, GC stress and SIGTERM")
                # the runtime's small functions: inlined, as calls with PYSTACHY_OPT=-jithelpers (#705)
                for setting, inline in [({}, True), ({"PYSTACHY_OPT": "-jithelpers"}, False), ({"PYSTACHY_GC_STRESS_PROGRAM": "1"}, True)]:
                    capture.unlink(missing_ok=True)
                    if run(cmd + ["run", str(helpers)], chosen | setting) != helpers_expected:
                        raise RuntimeError(f"{where}: {setting}: the runtime's small functions' results or errors differ from CPython")
                    executed = capture.read_text()
                    calls = [h for h in HELPERS if re.search(rf"\b(?:call|invoke)\b[^\n]*@{h}\(", executed)]
                    if inline and (calls or "available_externally" in executed):
                        raise RuntimeError(f"{where}: {setting}: the loop still calls {calls}, or a copy reached the JIT")
                    if not inline and calls != HELPERS:
                        raise RuntimeError(f"{where}: PYSTACHY_OPT=-jithelpers inlined {sorted(set(HELPERS) - set(calls))}")
                print(f"{where}: {len(HELPERS)} small runtime functions inlined into a loop, also under GC stress, and called with PYSTACHY_OPT=-jithelpers")
            for setting, invalid in [("PYSTACHY_JIT_CODEGEN", value) for value in ("", "1", "-O0", "0;false")] + \
                                    [("PYSTACHY_JIT_LAUNCHER", value) for value in ("", "LLI", "lljit", "auto;lli")]:
                invocation.unlink(missing_ok=True)
                codegen.unlink(missing_ok=True)
                rejected = subprocess.run(cmd + ["run", str(source)], cwd=ROOT,
                                          env=runners["lljit"] | {setting: invalid}, capture_output=True,
                                          timeout=60, check=False)
                if rejected.returncode == 0 or rejected.stdout or setting.encode() + b":" not in rejected.stderr or invocation.exists() or codegen.exists():
                    raise RuntimeError(f"{label}: invalid {setting}={invalid!r} was not rejected before the JIT")
            print(f"{label}: invalid code generation and runner settings rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
