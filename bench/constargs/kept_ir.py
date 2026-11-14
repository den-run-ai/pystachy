"""What constargs changes for each program: the IR that global dead-code elimination keeps.

For each program, the compiler emits LLVM IR with the pass on and with PYSTACHY_OPT=-constargs.
A function is kept if the module's data, a function that is not internal or a kept function
names it, which is what LLVM's globaldce keeps. The program is not run, and LLVM is not either.

usage: python3 bench/constargs/kept_ir.py [--compiler ./pystachy] [--jobs N] [--tsv OUT] FILE...
"""
import argparse
import concurrent.futures
import os
import re
import statistics
import subprocess
import sys
import tempfile

SYMBOL = re.compile(r'@("[^"]*"|[-A-Za-z0-9_.$]+)')


def kept(path):
    """(lines, functions) of the function text that the module's roots reach."""
    bodies, internal, top, name = {}, {}, [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if name is None:
                if line.startswith("define "):
                    name = SYMBOL.search(line).group(1)
                    bodies[name] = [line]
                    internal[name] = " internal " in line.split("@")[0] + " "
                else:
                    top.append(line)
            else:
                bodies[name].append(line)
                if line.startswith("}"):
                    name = None
    calls = {n: {m for line in lines for m in SYMBOL.findall(line) if m in bodies and m != n} for n, lines in bodies.items()}
    work = list({m for line in top for m in SYMBOL.findall(line) if m in bodies} | {n for n in bodies if not internal[n]})
    seen = set()
    while work:
        n = work.pop()
        if n not in seen:
            seen.add(n)
            work.extend(calls[n])
    return sum(len(bodies[n]) for n in seen), len(seen)


def measure(job):
    compiler, source = job
    row = []
    side = source[:-3] + ".path"
    root = os.path.dirname(os.path.abspath(compiler))
    for opt in ("-constargs", ""):
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
        env.update({"PYSTACHY_OPT": opt, "PYSTACHY_TIMING": "1"})
        if os.path.exists(side):
            with open(side) as f:
                env["PYSTACHY_PATH"] = ":".join(os.path.join(root, p) for p in f.read().strip().split(":"))
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([compiler, "ir", os.path.abspath(source), "-o", d + "/x.ll"], capture_output=True, text=True, env=env, cwd=root)
            if r.returncode != 0:
                return source, None
            times = {line.split("\t")[1]: float(line.split("\t")[2]) for line in r.stderr.splitlines() if line.startswith("pystachy-timing\t")}
            row.extend([*kept(d + "/x.ll"), times.get("program.frontend", 0.0)])
    return source, row


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--compiler", default="./pystachy")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--tsv", help="write each program's row here")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    rows = []
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for source, row in pool.map(measure, [(os.path.abspath(args.compiler), f) for f in args.files]):
            if row is not None:
                rows.append((source, *row))
    if args.tsv:
        with open(args.tsv, "w") as f:
            f.write("program\tlines_off\tfunctions_off\tfrontend_off\tlines_on\tfunctions_on\tfrontend_on\n")
            for row in rows:
                f.write("\t".join(str(x) for x in row) + "\n")
    if not rows:
        sys.exit("no program compiled")
    off, on = sum(r[1] for r in rows), sum(r[4] for r in rows)
    ratios = sorted(r[4] / r[1] for r in rows)
    print(f"{len(rows)} of {len(args.files)} programs compiled")
    print(f"kept IR lines: {off} -> {on} ({(on - off) * 100 / off:+.1f}%)")
    print(f"programs: {sum(r[4] < r[1] for r in rows)} smaller, {sum(r[4] > r[1] for r in rows)} larger, {sum(r[4] == r[1] for r in rows)} equal")
    print(f"kept ratio: median {statistics.median(ratios):.3f}, smallest {ratios[0]:.3f}")
    print(f"frontend seconds, summed: {sum(r[3] for r in rows):.1f} -> {sum(r[6] for r in rows):.1f}")
    for r in sorted(rows, key=lambda r: r[4] / r[1])[:10]:
        print(f"  {r[1]:7d} -> {r[4]:7d} ({r[4] * 100 // r[1]:3d}%)  {os.path.relpath(r[0])}")


if __name__ == "__main__":
    main()
