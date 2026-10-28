"""Check which of the runtime's opt-in code an AOT build keeps, without size or timing thresholds.

usage: python3 tools/aotprobe.py [-c LABEL=COMMAND]...
pystachy build defines pys_plain in the program's module, which -O2 optimizes with the runtime:
1 for a program that opts in to neither dynamic Any nor promoting ints, else 0 (runtime.c's
opt_in). A transparent clang wrapper captures the module the driver compiles, which must hold
that definition. A plain program that appends to, compares, hashes, looks up, formats and
prints lists, dicts, sets and tuples must keep none of the runtime's code for ints past 64 bits,
promoting ints and list identities (OPT_IN_ONLY: static functions and data that only such values
reach). The same program opting in to promoting ints (with ints past 64 bits in its containers)
or to dynamic Any must keep each of them, so that a renamed or inlined symbol fails here rather
than passes unseen. Every executable prints what CPython prints. The symbols are LLVM 18's on
Linux (CI's); another LLVM may inline differently.
"""
import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
PROGRAM = '''def show(xs: list[int], d: dict[int, int], s: set[int], keys: dict[tuple[int, str], int]) -> None:
    print(xs, d, sorted(s), keys)
    print(xs == [3, 1, 2], xs < [3, 2], 2 in xs, xs.index(1), xs.count(3))
    print(d == {3: 9, 1: 1}, d.get(3), 5 in d, list(d.keys()), list(d.values()))
    print(s == {1, 2, 3}, 2 in s, sorted(s | {7}), sorted(s & {1, 9}), sorted(s - {1}))
    print(keys[(1, "a")], (1, "a") in keys, hash((1, 2)) == hash((1, 2)), (1, 2) < (1, 3))
    print(f"{xs[0]:>4}|{d[3]:x}|{len(s):03d}", repr((xs, d)))


xs: list[int] = []
for i in [3, 1, 2]:
    xs.append(i)
xs.insert(0, 3)
xs.remove(3)
d: dict[int, int] = {}
for k in [3, 1]:
    d[k] = k * k
s: set[int] = set(xs)
keys: dict[tuple[int, str], int] = {(1, "a"): 10, (2, "b"): 20}
show(xs, d, s, keys)
print(d.pop(1), d.setdefault(4, 16), sorted(d.items()), (xs * 2)[3:])
'''
# ints past 64 bits in the containers of the program that opts in to promoting ints
BIG = '''big = 2 ** 70
xs.append(big)
d[big] = big
s.add(big)
keys[(big, "c")] = big
print(xs, d, sorted(s), keys[(big, "c")], big in xs, big in d, big in s, xs == xs[:])
print(f"{big:,}", repr((big, -big)), {(big, 1): 2} == {(big, 1): 2})
'''
INT = "# pystachy: python-int\n"
DYN = "# pystachy: dynamic-any\n"
# what only an int past 64 bits, a promoting int or a list's identity reaches (runtime.c): its
# repr's and float comparison's mpz code, a dict's and a set's lookups of such a key, the
# comparisons of promoting ints in containers and tuples, and the small-int boxes of identities
OPT_IN_ONLY = ["mpz_digits", "mpz_cmp_float", "big_eq", "dbfind", "sbfind", "jeq", "smallint"]


def run(command, env, cwd=ROOT):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=300, check=False)
    if result.returncode or result.stderr:
        raise RuntimeError(f"{shlex.join(command)}: exit {result.returncode}\n{result.stderr.decode()}")
    return result.stdout


def symbols(nm, exe):
    # the names the executable's symbol table defines, without Mach-O's leading underscore
    out = run([nm, "--defined-only", "-j", str(exe)], os.environ).decode().split()
    return {s[1:] if sys.platform == "darwin" and s.startswith("_") else s for s in out}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", action="append", default=[], metavar="LABEL=COMMAND")
    args = parser.parse_args()
    commands = args.c or [f"hosted={shlex.quote(sys.executable)} -m pystachy", f"native={ROOT / 'pystachy'}"]
    llvm = os.environ.get("PYSTACHY_LLVM", "")
    with tempfile.TemporaryDirectory(prefix="pystachy-aotprobe-") as tmp:
        temp = Path(tmp)
        sources = {"plain": PROGRAM, "python-int": INT + PROGRAM + BIG, "dynamic-any": DYN + PROGRAM}
        for name, text in sources.items():
            (temp / f"{name.replace('-', '_')}.py").write_text(text)
        capture = temp / "captured.bc"
        bindir = temp / "bin"
        bindir.mkdir()
        real = {}
        for name in ("clang", "opt", "lli", "llvm-link", "llvm-as", "llvm-dis", "llvm-nm"):
            path = shutil.which(str(Path(llvm) / name) if llvm else name)
            if path is None:
                raise RuntimeError(f"cannot find {name}; set PYSTACHY_LLVM")
            real[name] = str(Path(path).absolute())
            if name not in ("clang", "llvm-dis", "llvm-nm"):
                (bindir / name).symlink_to(real[name])
        # the driver's AOT step is clang -O2 -c <its temporary directory>/prog.bc: keep a copy of that
        wrapper = bindir / "clang"
        wrapper.write_text(f"#!/bin/sh\nfor a in \"$@\"; do case $a in */prog.bc) cp \"$a\" {shlex.quote(str(capture))} ;; esac; done\n"
                           f"exec {shlex.quote(real['clang'])} \"$@\"\n")
        wrapper.chmod(0o755)
        env = os.environ | {"PYSTACHY_LLVM": str(bindir)}
        for k in ("PYSTACHY_CFLAGS", "PYSTACHY_OPT", "PYSTACHY_PATH", "PYSTACHY_GC", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM"):
            env.pop(k, None)  # (-O0 or other passes would keep what the default build drops)
        expected = {name: run([sys.executable, f"{name.replace('-', '_')}.py"], env, temp) for name in sources}
        for spec in commands:
            label, command = spec.split("=", 1)
            cmd = shlex.split(command)
            kept = {}
            for name in sources:
                src = temp / f"{name.replace('-', '_')}.py"
                exe = temp / f"{label}-{name}"
                capture.unlink(missing_ok=True)
                run(cmd + ["build", str(src), "-o", str(exe)], env)
                if not capture.exists():
                    raise RuntimeError(f"{label} {name}: the AOT build compiled no prog.bc")
                ll = run([real["llvm-dis"], str(capture), "-o", "-"], env).decode()
                want = 1 if name == "plain" else 0
                got = re.findall(r"^@pys_plain = .*$", ll, re.M)
                if got != [f"@pys_plain = constant i64 {want}"]:
                    raise RuntimeError(f"{label} {name}: the AOT module defines {got}, expected pys_plain = {want}")
                if run([str(exe)], env, temp) != expected[name]:
                    raise RuntimeError(f"{label} {name}: the AOT executable's output differs from CPython's")
                kept[name] = symbols(real["llvm-nm"], exe) & set(OPT_IN_ONLY)
            if kept["plain"]:
                raise RuntimeError(f"{label}: the plain program's executable keeps opt-in runtime code: {sorted(kept['plain'])}")
            missing = set(OPT_IN_ONLY) - kept["python-int"] - kept["dynamic-any"]
            if missing:
                raise RuntimeError(f"{label}: no opt-in program's executable keeps {sorted(missing)}: update OPT_IN_ONLY")
            print(f"{label}: pys_plain 1, 0, 0; the plain executable keeps none of {len(OPT_IN_ONLY)} opt-in symbols, "
                  f"the python-int one {len(kept['python-int'])} and the dynamic-any one {len(kept['dynamic-any'])}; outputs as CPython's")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
