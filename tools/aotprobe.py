"""Check which of the runtime's opt-in code an AOT build keeps, without size or timing thresholds.

usage: python3 tools/aotprobe.py [-c LABEL=COMMAND]...
pystachy build defines pys_plain in the program's module, which -O2 optimizes with the runtime:
1 for a program that opts in to neither dynamic Any nor promoting ints, else 0 (runtime.c's
opt_in). A transparent clang wrapper captures the module the driver compiles, which must hold
that definition. A plain program that appends to, stores into, compares, hashes, looks up,
formats and prints lists, dicts, sets and tuples must keep none of the runtime's code for ints
past 64 bits, promoting ints and list identities (OPT_IN_ONLY: static functions and data that
only such values reach, including the code that keeps a list's identity companion in step). The
same program opting in to promoting ints (with ints past 64 bits in its containers)
or to dynamic Any collectively keep each of them, so that a renamed or inlined symbol fails here
rather than passes unseen. Wrappers importing those modules check that an imported opt-in also
keeps the feature paths available. Every executable prints what CPython prints. The symbols are LLVM 18's on
Linux (CI's); another LLVM may inline differently. A list store has no symbol of its own: in the
module -O2 makes of the captured one (the driver's own step, clang -O2), the plain program's
pys_list_set must store its item alone, and the python-int program's also its companion entry
and pending mark (STORE), so that the check sees them where they belong. That item store carries
lowering's "@slot" tag, which the driver gives runtime.c's accesses through struct Slot
(retag_runtime_lists), and the program's own loads of a list's length carry its "@list" tag: in
one module of one TBAA type each, LLVM tells an item from a length across inlined runtime code.

Allocations (allocelide, #1017): compiled code's objects that hold no reference (only ints,
floats and bools) come from pys_new, which -O2 sees as an allocation and deletes where nothing
keeps the object, before the late step inlines the allocator's fast path into the calls left. An
opt wrapper keeps the module -O2 gave that step (prog-opt.bc), where each allocation left is a
call of pys_new (the runtime's C code never calls it): TEMPS, whose vectors never leave walk(),
keeps none, and KEPT, whose objects a list keeps, does. With allocelide off there is no late step,
and with pys_new inlined before -O2 KEPT keeps no call: either fails here. KEPT also builds with
PYSTACHY_CFLAGS=-O0, whose runtime gives pys_new optnone, which the late step must drop too (LLVM's
verifier rejects optnone without noinline). HELD's holders, an object and a tuple that hold an
object each and that run() reads after collections, hold references: their allocations are
pys_alloc's, which -O2 never deletes, and only the objects they hold, which hold none, pys_new's.
Its executable, also with a collection at every allocation, keeps the held objects alive, as
CPython does: weak references to them stay alive (with the marked call, -O2 forwarded a holder's
fields across the collections and left the holder's address dead, and the collector freed them).

The allocation window (#650): WINDOW's executable makes about 150 MiB of small lists that die at
once, and collects more often with PYSTACHY_GC_MIN=1 and less with 256 than in the default 32 MiB
window; values out of range (0, negative, not a number, past 2**20) keep the default.
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
xs[-1] = 2
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
# comparisons of promoting ints in containers and tuples, the small-int boxes of identities, and
# the list code that keeps a companion in step: an append's, a copy's, and an emptied list's
OPT_IN_ONLY = ["mpz_digits", "mpz_cmp_float", "big_eq", "dbfind", "sbfind", "jeq", "smallint",
               "list_append_boxed", "list_identity_slow", "empty_identity_int", "empty_identity_float",
               "empty_identity_big"]
# the stores of -O2's pys_list_set (PROGRAM's xs[-1] = 2): the item's, and an opt-in program's
# companion entry and pending mark
LIST_SET = re.compile(r"^define [^\n]*@pys_list_set\(.*?^}$", re.M | re.S)
STORE = re.compile(r"^\s+store ", re.M)
TAGGED = re.compile(r"!tbaa !(\d+)")


def tag_base(ll: str, line: str) -> tuple[str, int]:
    """The struct type name and offset of the TBAA access tag that a load or store line names."""
    tag = TAGGED.search(line)
    if tag is None:
        return ("", -1)
    ops = re.search(rf"^!{tag.group(1)} = !{{(.*)}}$", ll, re.M).group(1).split(", ")
    name = re.search(rf"^{re.escape(ops[0])} = !{{!\"([^\"]*)\"", ll, re.M).group(1)
    return (name, int(ops[2][4:]))
# objects that never escape (allocelide: none is allocated) and objects that a list keeps (each is)
TEMPS = '''class Vec:
    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, other: "Vec") -> "Vec":
        return Vec(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec") -> "Vec":
        return Vec(self.x - other.x, self.y - other.y, self.z - other.z)

    def scale(self, f: float) -> "Vec":
        return Vec(f * self.x, f * self.y, f * self.z)

    def dot(self, other: "Vec") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z


def walk(n: int) -> float:
    o = Vec(0.5, -1.0, 2.0)
    d = Vec(0.25, 0.75, -0.5)
    c = Vec(1.0, 2.0, 3.0)
    m = Vec(0.0, 0.6, 0.8)
    acc = 0.0
    for i in range(n):
        p = o + d.scale(i * 1e-3)
        acc += (p - c).dot(m)
    return acc


print(walk(1000))
'''
KEPT = '''class Item:
    def __init__(self, x: float) -> None:
        self.x = x


def keep(n: int) -> list[Item]:
    kept: list[Item] = []
    for i in range(n):
        kept.append(Item(i * 0.5))
    return kept


print(sum([item.x for item in keep(1000)]))
'''
# holders, which hold references, that run() reads after collections, and the objects they hold,
# which hold none: weak references to those must stay alive
HELD = '''from _weakref import ref


class Item:
    def __init__(self, value: int) -> None:
        self.value = value


class Holder:
    def __init__(self, item: Item, tag: str) -> None:
        self.item = item
        self.tag = tag


def churn() -> None:
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


def run(n: int) -> None:
    h = Holder(Item(n), "h")
    t = (Item(n + 1), n * 2)
    rs = [ref(h.item), ref(t[0])]
    churn()
    print([r() is None for r in rs], h.tag, t[1])


run(1)
'''
# small lists that die at once: about 150 MiB of allocation, whose collections the allocation window
# between them sets (32 MiB, or PYSTACHY_GC_MIN's, #650)
WINDOW = '''def churn(n: int) -> int:
    total = 0
    for i in range(n):
        total += len([i, i + 1, i + 2])
    return total


print(churn(2000000))
'''
# the allocations of compiled code that -O2 left: its calls of pys_new
NEW = re.compile(r"call [^@\n]*@pys_new\(")
# HELD's run() as the compiler emits it, and the operands of its calls of pys_new and pys_alloc
RUN = re.compile(r"^define[^\n]*@f\.run\([^\n]*\n.*?^}", re.M | re.S)
NEWS = re.compile(r"call [^@\n]*@pys_new\(([^\n]*)")
ALLOCS = re.compile(r"call ptr @pys_alloc\(([^\n]*)")


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
        sources = {"plain": PROGRAM, "python-int": INT + PROGRAM + BIG, "dynamic-any": DYN + PROGRAM,
                   "python-int-import": "import python_int\n", "dynamic-any-import": "import dynamic_any\n"}
        for name, text in sources.items():
            (temp / f"{name.replace('-', '_')}.py").write_text(text)
        capture = temp / "captured.bc"
        late = temp / "opt.bc"
        bindir = temp / "bin"
        bindir.mkdir()
        real = {}
        for name in ("clang", "opt", "lli", "llvm-link", "llvm-as", "llvm-dis", "llvm-nm"):
            path = shutil.which(str(Path(llvm) / name) if llvm else name)
            if path is None:
                raise RuntimeError(f"cannot find {name}; set PYSTACHY_LLVM")
            real[name] = str(Path(path).absolute())
            if name not in ("clang", "opt", "llvm-dis", "llvm-nm"):
                (bindir / name).symlink_to(real[name])
        # the driver's AOT step is clang -O2 -c <its temporary directory>/prog.bc: keep a copy of that,
        # and of prog-opt.bc, the module -O2 made, which allocelide's late step (opt) reads
        wrapper = bindir / "clang"
        wrapper.write_text(f"#!/bin/sh\nfor a in \"$@\"; do case $a in */prog.bc) cp \"$a\" {shlex.quote(str(capture))} ;; esac; done\n"
                           f"exec {shlex.quote(real['clang'])} \"$@\"\n")
        wrapper.chmod(0o755)
        optimizer = bindir / "opt"
        optimizer.write_text(f"#!/bin/sh\nfor a in \"$@\"; do case $a in */prog-opt.bc) cp \"$a\" {shlex.quote(str(late))} ;; esac; done\n"
                             f"exec {shlex.quote(real['opt'])} \"$@\"\n")
        optimizer.chmod(0o755)
        env = os.environ | {"PYSTACHY_LLVM": str(bindir), "PYSTACHY_CACHE": str(temp / "cache")}
        for k in ("PYSTACHY_CFLAGS", "PYSTACHY_OPT", "PYSTACHY_PATH", "PYSTACHY_GC", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM"):
            env.pop(k, None)  # (-O0 or other passes would keep what the default build drops)
        expected = {name: run([sys.executable, f"{name.replace('-', '_')}.py"], env, temp) for name in sources}
        for spec in commands:
            label, command = spec.split("=", 1)
            cmd = shlex.split(command)
            kept = {}
            stores = {}
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
                if name in ("plain", "python-int"):
                    o2 = temp / f"{label}-{name}-O2.bc"
                    run([real["clang"], "-O2", "-c", "-emit-llvm", str(capture), "-o", str(o2)], env)
                    o2ll = run([real["llvm-dis"], str(o2), "-o", "-"], env).decode()
                    body = LIST_SET.search(o2ll)
                    if body is None:
                        raise RuntimeError(f"{label} {name}: the module -O2 made defines no pys_list_set")
                    stores[name] = len(STORE.findall(body.group(0)))
                    if name == "plain":
                        item = [ln for ln in body.group(0).split("\n") if STORE.match(ln)]
                        if [tag_base(o2ll, ln) for ln in item] != [("@slot", 0)]:
                            raise RuntimeError(f"{label}: -O2's pys_list_set stores its item with {[tag_base(o2ll, ln) for ln in item]}, "
                                               "expected lowering's @slot tag (retag_runtime_lists)")
                        lengths = [ln for ln in ll.split("\n") if re.match(r"^\s+%\S+ = load i64, ptr .*!range", ln)]
                        if ("@list", 0) not in [tag_base(ll, ln) for ln in lengths]:
                            raise RuntimeError(f"{label}: the program loads no list length with lowering's @list tag")
            if kept["plain"]:
                raise RuntimeError(f"{label}: the plain program's executable keeps opt-in runtime code: {sorted(kept['plain'])}")
            if stores["plain"] != 1 or stores["python-int"] < 2:
                raise RuntimeError(f"{label}: -O2's pys_list_set stores {stores['plain']} times in the plain program (its item "
                                   f"alone: 1) and {stores['python-int']} in the python-int one (its companion's too: 2 or more)")
            for suffix in ("", "-import"):
                missing = set(OPT_IN_ONLY) - kept["python-int" + suffix] - kept["dynamic-any" + suffix]
                if missing:
                    raise RuntimeError(f"{label}: opt-in programs{suffix} do not keep {sorted(missing)}: update OPT_IN_ONLY")
            print(f"{label}: pys_plain 1, 0, 0, 0, 0; the plain executable keeps none of {len(OPT_IN_ONLY)} opt-in symbols, "
                  f"the python-int one {len(kept['python-int'])} and the dynamic-any one {len(kept['dynamic-any'])}; outputs as CPython's")
            print(f"{label}: -O2's pys_list_set stores {stores['plain']} time in the plain program, "
                  f"{stores['python-int']} times in the python-int one")
            left = {}
            for name, text in (("temps", TEMPS), ("kept", KEPT)):
                src = temp / f"{name}.py"
                src.write_text(text)
                exe = temp / f"{label}-{name}"
                late.unlink(missing_ok=True)
                run(cmd + ["build", str(src), "-o", str(exe)], env)
                if not late.exists():
                    raise RuntimeError(f"{label} {name}: the AOT build had no late step (prog-opt.bc): is allocelide off?")
                left[name] = len(NEW.findall(run([real["llvm-dis"], str(late), "-o", "-"], env).decode()))
                if run([str(exe)], env, temp) != run([sys.executable, f"{name}.py"], env, temp):
                    raise RuntimeError(f"{label} {name}: the AOT executable's output differs from CPython's")
            if left["temps"] != 0:
                raise RuntimeError(f"{label}: objects that never escape stay allocated ({left['temps']} calls of pys_new after -O2)")
            if left["kept"] == 0:
                raise RuntimeError(f"{label}: no allocation left where a list keeps the objects: the check counts nothing")
            print(f"{label}: allocations after -O2: none where no object escapes, {left['kept']} where a list keeps them")
            exe = temp / f"{label}-kept-O0"
            late.unlink(missing_ok=True)
            run(cmd + ["build", str(temp / "kept.py"), "-o", str(exe)], env | {"PYSTACHY_CFLAGS": "-O0"})
            if not late.exists():
                raise RuntimeError(f"{label} kept with PYSTACHY_CFLAGS=-O0: the AOT build had no late step (prog-opt.bc)")
            if run([str(exe)], env, temp) != run([sys.executable, "kept.py"], env, temp):
                raise RuntimeError(f"{label} kept with PYSTACHY_CFLAGS=-O0: the AOT executable's output differs from CPython's")
            print(f"{label}: with PYSTACHY_CFLAGS=-O0 (a runtime whose pys_new is optnone), the late step runs and the output is CPython's")
            src = temp / "held.py"
            src.write_text(HELD)
            body = RUN.search(run(cmd + ["ir", str(src)], env).decode())
            if body is None:
                raise RuntimeError(f"{label} held: the IR defines no run()")
            news = NEWS.findall(body.group())
            allocs = ALLOCS.findall(body.group())
            if len(news) != 2 or any("%C.Item," not in a for a in news):
                raise RuntimeError(f"{label} held: run()'s pys_new calls are not the two held objects': {news}")
            if not any("%C.Holder," in a for a in allocs) or "i64 16)" not in allocs:
                raise RuntimeError(f"{label} held: run()'s holders do not come from pys_alloc: {allocs}")
            exe = temp / f"{label}-held"
            run(cmd + ["build", str(src), "-o", str(exe)], env)
            want = run([sys.executable, "held.py"], env, temp)
            for stress in ({}, {"PYSTACHY_GC_STRESS": "1"}):
                if run([str(exe)], env | stress, temp) != want:
                    raise RuntimeError(f"{label} held: the AOT executable's output differs from CPython's{' under GC stress' if stress else ''}: a holder's object was collected")
            print(f"{label}: held objects stay alive through collections, also under GC stress; their holders come from pys_alloc, the objects from pys_new")
            src = temp / "window.py"
            src.write_text(WINDOW)
            exe = temp / f"{label}-window"
            run(cmd + ["build", str(src), "-o", str(exe)], env)
            want = run([sys.executable, "window.py"], env, temp)
            counts = {}
            for setting in ("", "1", "256", "0", "-4", "x", "1048577"):
                result = subprocess.run([str(exe)], cwd=temp, env=env | {"PYSTACHY_GC": "stats", "PYSTACHY_GC_MIN": setting},
                                        capture_output=True, timeout=300, check=False)
                stats = re.search(rb"^gc: (\d+) collections", result.stderr, re.M)
                if result.returncode or result.stdout != want or stats is None:
                    raise RuntimeError(f"{label} window with PYSTACHY_GC_MIN={setting!r}: exit {result.returncode}, output {result.stdout!r}, stderr {result.stderr.decode()}")
                counts[setting] = int(stats.group(1))
            if not counts["1"] > counts[""] > counts["256"] or counts[""] < 2:
                raise RuntimeError(f"{label} window: PYSTACHY_GC_MIN does not set the window between collections: {counts}")
            if any(counts[v] != counts[""] for v in ("0", "-4", "x", "1048577")):
                raise RuntimeError(f"{label} window: an invalid PYSTACHY_GC_MIN changed the window: {counts}")
            print(f"{label}: collections over 150 MiB of small lists: {counts['']} in the default 32 MiB window, {counts['1']} with PYSTACHY_GC_MIN=1, {counts['256']} with 256; invalid values keep the default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
