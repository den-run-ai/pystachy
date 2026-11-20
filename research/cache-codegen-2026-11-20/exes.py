"""Interleaved, pinned runs of prebuilt executables of one program (argv[0] the source).
usage: exes.py ROUNDS OUT.json SRC ARGS... -- NAME=EXE..."""
import json, os, re, statistics, subprocess, sys
rounds, out = int(sys.argv[1]), sys.argv[2]
k = sys.argv.index("--")
src, args = sys.argv[3], sys.argv[4:k]
exes = dict(a.split("=", 1) for a in sys.argv[k + 1:])
names = list(exes)
base = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
runs = {n: [] for n in names}
ref = None
for r in range(rounds):
    for n in names[r % len(names):] + names[:r % len(names)]:
        p = subprocess.run([src, *args], executable=exes[n], env=base, capture_output=True, stdin=subprocess.DEVNULL,
                           preexec_fn=lambda: os.sched_setaffinity(0, {1}))
        if p.returncode:
            sys.exit(f"{n}: exit {p.returncode}")
        if ref is None:
            ref = p.stdout
        elif p.stdout != ref:
            sys.exit(f"{n}: stdout differs")
        err = p.stderr.decode()
        row = {k: float(x) for k, x in re.findall(r"\b(knn|layout)=([0-9]+\.[0-9]+)", err)}
        m = re.findall(r"^seconds ([0-9.e-]+)$", err, flags=re.M)
        if m:
            row["seconds"] = sum(float(x) for x in m)
        runs[n].append(row)
json.dump({"exes": exes, "rounds": rounds, "runs": runs}, open(out, "w"), indent=1)
for n in names:
    for key in sorted(runs[n][0]):
        med = statistics.median(row[key] for row in runs[n])
        paired = statistics.median(a[key] / b[key] for a, b in zip(runs[n], runs[names[0]]))
        print(f"{n:12} {key:8} median {med:.4f}  paired/{names[0]} {paired:.3f}", flush=True)
