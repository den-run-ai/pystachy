"""Opt-in sweep: does adding '# pystachy: dynamic-any' to a passing corpus program keep it passing?

usage: python3.13 optin_sweep.py OUT_DIR [JOBS [AREA]]   (run from anywhere; ROOT is the checkout)

For every tests/programs/AREA/NAME.py (not NAME.full ones, not SIGINT cases), two copies go to
OUT_DIR/{plain,dyn}/AREA/NAME.py, the second with the comment as its first line, and each runs as
tests/run.sh's JIT mode runs a program: `pystachy run COPY a1 a2` from the checkout, stdin NAME.in,
PYSTACHY_PATH from NAME.path (after the program's own directory, which the copy left), stdout plus
"[exit N]" compared with NAME.out, stderr's last line with NAME.err (or no stderr). A regression is a
program whose plain copy passes and whose copy with the comment does not.
"""
import concurrent.futures
import json
import os
import subprocess
import sys

ROOT = os.environ.get("PYSTACHY_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PYS = os.path.join(ROOT, "pystachy")
PRAGMA = "# pystachy: dynamic-any\n"


def run(copy: str, b: str, origdir: str) -> tuple[bool, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_IRCHECK"] = "1"
    mp = open(b + ".path").read().strip() if os.path.exists(b + ".path") else ""
    env["PYSTACHY_PATH"] = origdir + (":" + mp if mp else "")
    stdin = open(b + ".in", "rb") if os.path.exists(b + ".in") else subprocess.DEVNULL
    try:
        p = subprocess.run([PYS, "run", copy, "a1", "a2"], stdin=stdin, capture_output=True, cwd=ROOT, env=env, timeout=180)
        out, err, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        return False, "timeout"
    finally:
        if stdin is not subprocess.DEVNULL:
            stdin.close()
    got = out + b"[exit %d]\n" % rc
    want = open(b + ".out", "rb").read()
    lines = [ln for ln in err.decode("utf-8", "replace").splitlines()]
    last = lines[-1] if lines else ""
    if os.path.exists(b + ".err"):
        err_ok = last == open(b + ".err", encoding="utf-8", errors="replace").read().rstrip("\n")
    else:
        err_ok = len(err) == 0
    if got == want and err_ok:
        return True, ""
    diag = next((ln for ln in lines if ": error: " in ln), last)
    if got != want and diag == "":
        w, g = want.decode("utf-8", "replace").splitlines(), got.decode("utf-8", "replace").splitlines()
        for i in range(max(len(w), len(g))):
            a = w[i] if i < len(w) else "<none>"
            c = g[i] if i < len(g) else "<none>"
            if a != c:
                diag = "stdout line %d: want %r, got %r" % (i + 1, a[:120], c[:120])
                break
    return False, diag.strip()


def one(path: str, outdir: str) -> dict:
    b = path[:-3]
    rel = os.path.relpath(path, os.path.join(ROOT, "tests/programs"))
    src = open(path, encoding="utf-8", errors="surrogateescape").read()
    res = {"program": rel}
    for variant, text in (("plain", src), ("dyn", PRAGMA + src)):
        copy = os.path.join(outdir, variant, rel)
        os.makedirs(os.path.dirname(copy), exist_ok=True)
        with open(copy, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.write(text)
        ok, diag = run(copy, b, os.path.dirname(path))
        res[variant] = ok
        if not ok:
            res[variant + "_diag"] = diag.replace(outdir + "/", "")
    return res


def main() -> None:
    outdir = os.path.abspath(sys.argv[1])
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    progs = []
    base = os.path.join(ROOT, "tests/programs")
    only = sys.argv[3] if len(sys.argv) > 3 else ""
    for area in sorted(os.listdir(base)):
        if only and area != only:
            continue
        d = os.path.join(base, area)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".py") and os.path.exists(os.path.join(d, fn[:-3] + ".out")):
                if os.path.exists(os.path.join(d, fn[:-3] + ".full")) or "sigint" in fn:
                    continue
                progs.append(os.path.join(d, fn))
    results = []
    with concurrent.futures.ThreadPoolExecutor(jobs) as ex:
        for r in ex.map(lambda p: one(p, outdir), progs):
            results.append(r)
            if r["plain"] and not r["dyn"]:
                print("REGRESSION", r["program"], "|", r.get("dyn_diag", ""), flush=True)
    summary = {
        "programs": len(results),
        "plain_pass": sum(r["plain"] for r in results),
        "dyn_pass": sum(r["dyn"] for r in results),
        "regressions": [r for r in results if r["plain"] and not r["dyn"]],
        "fixed_by_comment": [r["program"] for r in results if r["dyn"] and not r["plain"]],
        "plain_failures": [r for r in results if not r["plain"]],
    }
    with open(os.path.join(outdir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print("programs %d, plain pass %d, with the comment pass %d, regressions %d, fixed %d" % (
        summary["programs"], summary["plain_pass"], summary["dyn_pass"], len(summary["regressions"]), len(summary["fixed_by_comment"])))


main()
