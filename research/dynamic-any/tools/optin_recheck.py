"""Re-check the opt-in sweep's regressions differentially: the copy with the comment (after a byte
order mark, if any) under CPython 3.13.16 and under `pystachy run`, from the checkout, with the
program's stdin, module path and arguments as tests/run.sh gives them. A regression stands only where
the two differ (stdout plus exit status, or stderr's last line) on the same file.

usage: python3.13 optin_recheck.py SWEEP_DIR
"""
import json
import os
import subprocess
import sys

ROOT = os.environ.get("PYSTACHY_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PRAGMA = "# pystachy: dynamic-any\n"


def run(cmd, b, env):
    stdin = open(b + ".in", "rb") if os.path.exists(b + ".in") else subprocess.DEVNULL
    try:
        p = subprocess.run(cmd, stdin=stdin, capture_output=True, cwd=ROOT, env=env, timeout=120)
    except subprocess.TimeoutExpired:
        return b"timeout", "timeout", ["timeout (120 s)"]
    finally:
        if stdin is not subprocess.DEVNULL:
            stdin.close()
    lines = p.stderr.decode("utf-8", "replace").splitlines()
    return p.stdout + b"[exit %d]\n" % p.returncode, (lines[-1] if lines else ""), lines


def main() -> None:
    sweep = os.path.abspath(sys.argv[1])
    summary = json.load(open(os.path.join(sweep, "summary.json")))
    out = []
    for r in summary["regressions"]:
        rel = r["program"]
        orig = os.path.join(ROOT, "tests/programs", rel)
        b = orig[:-3]
        src = open(orig, encoding="utf-8", errors="surrogateescape").read()
        bom = "﻿" if src.startswith("﻿") else ""
        text = bom + PRAGMA + src[len(bom):]
        copy = os.path.join(sweep, "recheck", rel)
        os.makedirs(os.path.dirname(copy), exist_ok=True)
        with open(copy, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.write(text)
        mp = open(b + ".path").read().strip() if os.path.exists(b + ".path") else ""
        path = os.path.dirname(orig) + (":" + mp if mp else "")
        cenv = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_") and k != "PYTHONPATH"}
        cenv["PYTHONPATH"] = path
        penv = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
        penv["PYSTACHY_PATH"] = path
        penv["PYSTACHY_IRCHECK"] = "1"
        cout, clast, _ = run(["python3.13", copy, "a1", "a2"], b, cenv)
        pout, plast, plines = run([os.path.join(ROOT, "pystachy"), "run", copy, "a1", "a2"], b, penv)
        same = cout == pout and clast == plast
        diag = next((ln for ln in plines if ": error: " in ln), plast)
        out.append({"program": rel, "stands": not same, "pystachy": diag.replace(sweep + "/", "")[:300],
                    "cpython_last_stderr": clast[:200]})
        print(("STANDS  " if not same else "ARTIFACT"), rel, "|", diag.replace(sweep + "/", "")[:200], flush=True)
    with open(os.path.join(sweep, "recheck.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("regressions that stand: %d of %d flagged" % (sum(o["stands"] for o in out), len(out)))


main()
