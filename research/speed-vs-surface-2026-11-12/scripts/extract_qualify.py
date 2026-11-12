"""Extract CPython unittest methods once (frozen extractor) and qualify them under CPython once.

usage: python3.13 -I extract_qualify.py CPYTHON_SRC WORKDIR OUT.json [-j N]

The extraction and the CPython oracle do not depend on the Pystachy commit under test, so they
are computed once; per-commit runs (method_sweep.py) compare each compiler's `run` output with
the stored CPython (exit status, stdout, stderr), exactly like `cpython_test_methods.py triage`.
"""
import concurrent.futures
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "frozen"))
import cpython_test_methods as ctm  # noqa: E402


def main():
    args = sys.argv[1:]
    jobs = 3
    if "-j" in args:
        i = args.index("-j")
        jobs = int(args[i + 1])
        del args[i:i + 2]
    src, workdir, out = args
    manifest = (HERE / "frozen" / "core-methods.sha256").read_text().split("\n")
    files = [line.split(None, 1)[1].strip() for line in manifest if line.strip()]
    work, left_out, errors = [], {}, {}
    for rel in files:
        f = os.path.join(src, rel)
        name = Path(f).stem
        parent = Path(f).parent.name
        d = os.path.join(os.path.abspath(workdir), parent + "." + name if parent != "test" else name)
        try:
            tests, left = ctm.extract(f, d)
        except (OSError, SyntaxError, UnicodeDecodeError, RecursionError) as e:
            errors[rel] = f"{type(e).__name__}: {e}"
            continue
        left_out[rel] = [list(x) for x in left]
        work += [(rel, c, m, os.path.join(d, f"{c}__{m}.py")) for c, m in tests]
    print(f"extracted {len(work)} methods from {len(files) - len(errors)} files; {len(errors)} errors",
          file=sys.stderr)

    def qualify(w):
        rel, c, m, prog = w
        r = ctm.run([sys.executable, "-I", prog], 120, cwd=os.path.dirname(prog))
        rec = {"file": rel, "test": f"{c}.{m}", "program": prog}
        if r[0] != 0:
            return rec | {"cpython": "fail", "detail": ctm.first_error(r[2])}
        if r[1].splitlines()[-1:] != [f"ok {c}.{m}"]:
            return rec | {"cpython": "fail", "detail": "success marker not reached"}
        return rec | {"cpython": "ok", "expected": list(r)}

    with concurrent.futures.ThreadPoolExecutor(jobs) as ex:
        records = list(ex.map(qualify, work))
    ok = sum(r["cpython"] == "ok" for r in records)
    print(f"qualified {ok} of {len(records)} under {sys.version.split()[0]}", file=sys.stderr)
    with open(out, "w") as fh:
        json.dump({"python": sys.version, "records": records, "left_out": left_out, "errors": errors}, fh, indent=1)


if __name__ == "__main__":
    main()
