"""Record CPython's stdout (the correctness oracle) for each frozen perf benchmark.

usage: python3.13 -I cpython_ref.py PERF_SPECS.json PERFROOT OUT.json
"""
import json
import subprocess
import sys
import time


def main():
    specs_path, root, out = sys.argv[1:]
    specs = json.load(open(specs_path))
    ref = {}
    for name, spec in specs.items():
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, spec["src"]] + spec["args"], cwd=root, capture_output=True, text=True,
                           timeout=600)
        wall = time.monotonic() - t0
        ref[name] = {"rc": p.returncode, "stdout": p.stdout, "stderr_tail": p.stderr[-300:], "wall_s": wall}
        print(f"{name:22s} rc={p.returncode} wall={wall:6.2f}s stdout={len(p.stdout)}B", file=sys.stderr)
    json.dump({"python": sys.version, "ref": ref}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
