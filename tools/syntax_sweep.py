"""Compare the SyntaxErrors Pystachy reports with CPython's, without compiling anything.

usage: python3 -I tools/syntax_sweep.py [--compiler C] PATH ...
Each PATH is a .py file, a directory (every .py file under it), or a .txt file of snippets
separated by lines "----"; a snippet is checked as a module, as the body of a function, of a
method and of a class. CPython's compile() is the reference (it never runs what it reads); the
compiler (default ./pystachy; "python3 pystachy.py" works too) runs "check", which parses the
file with the checks CPython makes before running a file and compiles nothing. Prints each case
whose verdicts differ (the SyntaxError's line and message, or none), then the counts. Valid code
Pystachy cannot parse (tabs in indentation, \\N{...} escapes, an f-string field reusing its quote)
counts apart.
"""
import concurrent.futures
import os
import re
import shlex
import subprocess
import sys
import tempfile
import warnings

CONTEXTS = ["module", "function", "method", "class"]


def indent(s, n):
    return "".join(" " * n + l if l.strip() else l for l in s.splitlines(True))


def in_context(src, ctx):
    if ctx == "function":
        return "def f(x):\n" + indent(src, 4) + "\n"
    if ctx == "method":
        return "class C:\n    def m(self, x):\n" + indent(src, 8) + "\n"
    if ctx == "class":
        return "class C:\n" + indent(src, 4) + "\n"
    return src


def cpython(raw, name):
    try:
        compile(raw, name, "exec")
        return "OK"
    except SyntaxError as e:
        return f"{e.lineno}: {e.msg}"
    except ValueError as e:  # (a null byte)
        return f"?: {e}"


def pystachy(cmd, path):
    r = subprocess.run(cmd + ["check", path], capture_output=True, text=True, errors="replace")
    if r.returncode == 0:
        return "OK"
    last = (r.stderr.strip().splitlines() or ["?"])[-1]
    m = re.match(r".*?:(\d+): error: (.*)", last)
    return f"{m.group(1)}: {m.group(2)}" if m else last


def check(cmd, path, raw, label):
    return label, cpython(raw, path), pystachy(cmd, path)


def main():
    warnings.simplefilter("ignore")  # (compile()'s SyntaxWarnings and DeprecationWarnings)
    args = sys.argv[1:]
    cmd = ["./pystachy"]
    if len(args) > 1 and args[0] == "--compiler":
        cmd = shlex.split(args[1])
        args = args[2:]
    if len(args) == 0:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    if os.path.exists(cmd[-1]):
        cmd[-1] = os.path.abspath(cmd[-1])  # (the snippets are checked in a temporary directory)
    tmp = tempfile.mkdtemp()
    jobs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as ex:
        for arg in args:
            files = [arg]
            if os.path.isdir(arg):
                files = []
                for dp, dn, fn in os.walk(arg):
                    dn.sort()
                    files += [os.path.join(dp, f) for f in sorted(fn) if f.endswith(".py")]
            for p in files:
                if not p.endswith(".txt"):
                    with open(p, "rb") as f:
                        jobs.append(ex.submit(check, cmd, p, f.read(), p))
                    continue
                with open(p) as f:
                    snippets = [s for s in f.read().split("----\n") if s.strip() != ""]
                for i, s in enumerate(snippets):
                    for ctx in CONTEXTS:
                        q = os.path.join(tmp, f"{len(jobs)}.py")
                        src = in_context(s, ctx)
                        with open(q, "w") as f:
                            f.write(src)
                        jobs.append(ex.submit(check, cmd, q, src, f"{p} #{i} ({ctx}): {s.strip()[:60]!r}"))
        same = 0
        unparsed = 0
        for j in jobs:
            label, want, got = j.result()
            if want == got:
                same += 1
            elif want == "OK" and ("not supported" in got or "unexpected character" in got):
                unparsed += 1
            else:
                print(f"{label}\n    cpython : {want}\n    pystachy: {got}")
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    print(f"{same} of {len(jobs)} agree, {unparsed} valid ones Pystachy cannot parse, {len(jobs) - same - unparsed} differ")


if __name__ == "__main__":
    main()
