"""Differential probe runner: CPython 3.13 vs pystachy (JIT and/or AOT).

usage: python3.13 probe.py [--modes jit,aot] [--path DIR[:DIR]] [--out RESULTS_DIR] PROBE.py...

For each probe: runs CPython (-I, the probe's own directory and --path appended to sys.path, so
that stdlib modules are never shadowed), then `pystachy run` / `pystachy build`+exec with
PYSTACHY_PATH=--path, and reports whether stdout+exit status match; otherwise the first line of
pystachy's stderr (the compile error or the runtime error). NAME.in is stdin when present.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.environ.get("PYSTACHY_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PYS = os.path.join(ROOT, "pystachy")
CPY = os.environ.get("PYTHON", "python3.13")


def run(cmd, stdin, env=None, timeout=120):
    try:
        p = subprocess.run(cmd, input=stdin, capture_output=True, timeout=timeout, env=env)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return "timeout", b"", b"timeout"


KEEP: set[str] = set()


def clean_env(path):
    # (inherited PYSTACHY_* settings would change what is measured; --keep names those to pass on)
    env = {k: v for k, v in os.environ.items() if (not k.startswith("PYSTACHY_") or k in KEEP) and k != "PYTHONPATH"}
    if path:
        env["PYSTACHY_PATH"] = path
    return env


def first_line(err: bytes) -> str:
    lines = [ln for ln in err.decode("utf-8", "replace").splitlines() if ln.strip()]
    # the diagnostic line (FILE:LINE: error: ...) or the exception's last line
    for ln in lines:
        if ": error: " in ln:
            return ln.strip()
    return lines[-1].strip() if lines else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="jit")
    ap.add_argument("--path", default="")
    ap.add_argument("--cpath", default=None, help="CPython's module path (default: --path)")
    ap.add_argument("--out", default="")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--keep", default="", help="PYSTACHY_* settings to pass on, comma-separated (e.g. PYSTACHY_GC_STRESS_PROGRAM)")
    ap.add_argument("probes", nargs="+")
    a = ap.parse_args()
    KEEP.update(k for k in a.keep.split(",") if k)
    modes = a.modes.split(",")
    results = []
    for probe in a.probes:
        probe = os.path.abspath(probe)
        name = os.path.basename(probe)[:-3]
        inp = b""
        if os.path.exists(probe[:-3] + ".in"):
            with open(probe[:-3] + ".in", "rb") as f:
                inp = f.read()
        cpath = a.path if a.cpath is None else a.cpath
        dirs = [os.path.dirname(probe)] + [d for d in cpath.split(":") if d]
        boot = "import sys, runpy; sys.argv = [%r]; sys.path.extend(%r); runpy.run_path(%r, run_name='__main__')" % (probe, dirs, probe)
        crc, cout, cerr = run([CPY, "-I", "-c", boot], inp, timeout=a.timeout)
        row = {"probe": name, "cpython_rc": crc, "cpython_out_sha": hashlib.sha256(cout).hexdigest()[:12]}
        if crc != 0:
            row["cpython_err"] = first_line(cerr)
        env = clean_env(":".join(d for d in a.path.split(":") if d))
        for m in modes:
            if m == "jit":
                rc, out, err = run([PYS, "run", probe], inp, env=env, timeout=a.timeout)
            else:
                exe = os.path.join(tempfile.mkdtemp(prefix="probe-"), name)
                brc, bout, berr = run([PYS, "build", probe, "-o", exe], b"", env=env, timeout=a.timeout)
                if brc != 0:
                    rc, out, err = brc, bout, berr
                else:
                    xenv = dict(env)
                    if env.get("PYSTACHY_GC_STRESS_PROGRAM"):   # (an AOT program reads its interval at run time, as tests/run.sh's XENV)
                        xenv["PYSTACHY_GC_STRESS"] = env["PYSTACHY_GC_STRESS_PROGRAM"]
                    rc, out, err = run([exe], inp, env=xenv, timeout=a.timeout)
                try:
                    os.unlink(exe)
                except OSError:
                    pass
                shutil.rmtree(os.path.dirname(exe), ignore_errors=True)
            same = rc == crc and out == cout
            row[m] = "PASS" if same else "FAIL"
            if not same:
                row[m + "_rc"] = rc
                row[m + "_err"] = first_line(err)
                if rc == crc and out != cout:
                    # where the outputs first differ
                    cl, pl = cout.decode("utf-8", "replace").splitlines(), out.decode("utf-8", "replace").splitlines()
                    for i in range(max(len(cl), len(pl))):
                        c = cl[i] if i < len(cl) else "<none>"
                        p = pl[i] if i < len(pl) else "<none>"
                        if c != p:
                            row[m + "_diff"] = "line %d: cpython %r / pystachy %r" % (i + 1, c[:160], p[:160])
                            break
            if a.out:
                os.makedirs(a.out, exist_ok=True)
                with open(os.path.join(a.out, "%s.%s.out" % (name, m)), "wb") as f:
                    f.write(out)
                with open(os.path.join(a.out, "%s.%s.err" % (name, m)), "wb") as f:
                    f.write(err)
        if a.out:
            with open(os.path.join(a.out, "%s.cpython.out" % name), "wb") as f:
                f.write(cout)
        results.append(row)
        status = " ".join("%s=%s" % (m, row[m]) for m in modes)
        print("%-34s cpy_rc=%s %s" % (name, crc, status))
        for m in modes:
            if row[m] != "PASS":
                print("    %s: rc=%s %s" % (m, row.get(m + "_rc"), row.get(m + "_err") or row.get(m + "_diff", "")))
        if crc != 0:
            print("    cpython: %s" % row.get("cpython_err"))
        sys.stdout.flush()
    if a.out:
        with open(os.path.join(a.out, "summary.json"), "w") as f:
            json.dump(results, f, indent=1)


main()
