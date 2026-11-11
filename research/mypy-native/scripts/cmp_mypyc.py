"""Compare one program under CPython, Pystachy AOT and mypyc 2.4.1: output, build and run time.
usage: cmp_mypyc.py PROGRAM.py PYSTACHY MYPYC_VENV_PYTHON [RUNS]"""
import os, shutil, statistics, subprocess, sys, tempfile, time
prog, pystachy, mpy = sys.argv[1], sys.argv[2], sys.argv[3]
runs = int(sys.argv[4]) if len(sys.argv) > 4 else 3

def timed(cmd, **kw):
    t = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return time.monotonic() - t, r

def median_run(cmd, **kw):
    ts, out = [], None
    for _ in range(runs):
        dt, r = timed(cmd, **kw)
        assert r.returncode == 0, (cmd, r.stderr[-2000:])
        ts.append(dt)
        out = r.stdout
    return statistics.median(ts), out

env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
with tempfile.TemporaryDirectory() as tmp:
    name = "prog_" + os.path.basename(prog)[:-3].replace("-", "_")
    src = os.path.join(tmp, name + ".py")
    shutil.copy(prog, src)
    cpy_t, cpy_out = median_run([sys.executable, "-I", src])
    bt, r = timed([pystachy, "build", src, "-o", os.path.join(tmp, "native")], env=env)
    assert r.returncode == 0, r.stderr[-2000:]
    pys_t, pys_out = median_run([os.path.join(tmp, "native")])
    mt, r = timed([os.path.join(os.path.dirname(mpy), "mypyc"), name + ".py"], cwd=tmp)
    assert r.returncode == 0, (r.stdout[-3000:], r.stderr[-2000:])
    os.remove(src)  # (import the extension, not the source)
    myc_t, myc_out = median_run([mpy, "-c", f"import {name}"], cwd=tmp)
    same = cpy_out == pys_out == myc_out
    print(f"{os.path.basename(prog)}: output {'identical' if same else 'DIFFERS'}; build pystachy {bt:.1f} s, mypyc {mt:.1f} s; run (median of {runs}) cpython {cpy_t:.3f} s, pystachy {pys_t:.3f} s, mypyc {myc_t:.3f} s")
    if not same:
        print("cpython:", cpy_out[:200], "pystachy:", pys_out[:200], "mypyc:", myc_out[:200])
