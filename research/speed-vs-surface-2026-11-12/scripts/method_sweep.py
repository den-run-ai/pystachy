"""Run the frozen, CPython-qualified CPython test methods through one Pystachy checkout's JIT.

usage: python3.13 -I method_sweep.py CHECKOUT QUALIFIED.json OUT.json [-j N] [--timeout S]

Classification follows tools/cpython_test_methods.py triage (frozen copy): match, match-python-int
(matches once `# pystachy: python-int` is prepended after a 64-bit failure), compile-error (non-zero
exit, no stdout and an ": error: " diagnostic), differs, or timeout. The compiler runs from the
checkout root with PYSTACHY_* settings removed and the program cache off.
"""
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "frozen"))
import cpython_test_methods as ctm  # noqa: E402


def main():
    args = sys.argv[1:]
    opts = {"-j": "2", "--timeout": "120", "--env": "", "--prepend": ""}
    for k in list(opts):
        if k in args:
            i = args.index(k)
            opts[k] = args[i + 1]
            del args[i:i + 2]
    checkout, qualified, out = args
    jobs, timeout = int(opts["-j"]), float(opts["--timeout"])
    checkout = os.path.abspath(checkout)
    compiler = [os.path.join(checkout, "pystachy")]
    tag = os.path.basename(checkout)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    env["PYSTACHY_PROGRAM_CACHE"] = "0"
    for kv in filter(None, opts["--env"].split(",")):
        k, v = kv.split("=", 1)
        env[k] = v
    data = json.load(open(qualified))
    work = [r for r in data["records"] if r["cpython"] == "ok"]

    def native(prog, expected):
        n = ctm.run(compiler + ["run", prog], timeout, cwd=checkout, env=env)
        if n[0] is None:
            return {"status": "timeout"}
        if list(n) == expected:
            return {"status": "match"}
        if n[0] != 0 and not n[1] and ": error: " in n[2]:
            return {"status": "compile-error", "detail": ctm.first_error(n[2])}
        return {"status": "differs", "exit": n[0], "detail": (n[1][-300:] + " | " + n[2][-500:]).strip()}

    head = opts["--prepend"].replace("\\n", "\n")
    if head and not head.endswith("\n"):
        head += "\n"

    def one(rec):
        t0 = time.monotonic()
        prog = rec["program"]
        if head:
            prog = rec["program"][:-3] + f"__pre_{tag}.py"
            Path(prog).write_text(head + Path(rec["program"]).read_text())
        r = native(prog, rec["expected"])
        if r["status"] != "match" and "fit in 64 bits" in r.get("detail", ""):
            wide = rec["program"][:-3] + f"__pyint_{tag}.py"
            Path(wide).write_text("# pystachy: python-int\n" + head + Path(rec["program"]).read_text())
            retry = native(wide, rec["expected"])
            os.unlink(wide)
            r["python_int_retry"] = retry["status"]
            if retry["status"] == "match":
                r["status"] = "match-python-int"
        if head:
            os.unlink(prog)
        r["seconds"] = round(time.monotonic() - t0, 3)
        return {"file": rec["file"], "test": rec["test"]} | r

    t0 = time.monotonic()
    # warm the runtime cache once so the first program does not pay for it inside a timeout
    warm = HERE / "warm.py"
    warm.write_text("print('warm')\n")
    ctm.run(compiler + ["run", str(warm)], 900, cwd=checkout, env=env)
    with concurrent.futures.ThreadPoolExecutor(jobs) as ex:
        records = list(ex.map(one, work))
    totals = {}
    for r in records:
        totals[r["status"]] = totals.get(r["status"], 0) + 1
    with open(out, "w") as fh:
        json.dump({"checkout": checkout, "totals": totals, "elapsed": time.monotonic() - t0,
                   "records": records}, fh, indent=0)
    print(tag, json.dumps(totals, sort_keys=True), f"{time.monotonic() - t0:.0f}s")


if __name__ == "__main__":
    main()
