import subprocess, sys, time, os
def t(cmd, env=None):
    e = dict(os.environ); e.update(env or {})
    t0 = time.perf_counter()
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=e)
    return time.perf_counter() - t0, r.returncode
P = __import__("os").environ.get("PYSTACHY", "./pystachy")  # the compiler under test
for f in sys.argv[1:]:
    cp = min(t(["python3.13", f + ".py"])[0] for _ in range(3))
    nc = [t([P, "run", f + ".py"], {"PYSTACHY_PROGRAM_CACHE": "0"}) for _ in range(3)]
    miss = t([P, "run", f + ".py"])
    hit = min(t([P, "run", f + ".py"])[0] for _ in range(3))
    aot = t([P, "build", f + ".py", "-o", f + ".aot"])
    ex = min(t(["./" + f + ".aot"])[0] for _ in range(3)) if aot[1] == 0 else -1
    irt = t([P, "ir", f + ".py", "-o", "/dev/null"])
    size = os.path.getsize(f + ".aot") if aot[1] == 0 else 0
    print(f"{f:13} cpython {cp*1000:6.0f} ms | frontend(ir) {irt[0]*1000:6.0f} ms | jit(no cache) {min(x[0] for x in nc)*1000:6.0f} ms rc={nc[0][1]} | cache miss {miss[0]*1000:6.0f} hit {hit*1000:5.0f} ms | aot build {aot[0]*1000:6.0f} ms, run {ex*1000:5.1f} ms, exe {size//1024} KiB")
