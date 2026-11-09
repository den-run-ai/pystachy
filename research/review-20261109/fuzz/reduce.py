"""Line/block reducer: keep deleting statements while Pystachy still reports the same error text
(or, with --diff, while CPython and Pystachy outputs still differ) and CPython still runs the file."""
import subprocess, sys, ast

P = __import__("os").environ.get("PYSTACHY", "./pystachy")  # the compiler under test
path, needle = sys.argv[1], sys.argv[2]
src = open(path).read().split("\n")


def interesting(lines):
    text = "\n".join(lines) + "\n"
    try:
        ast.parse(text)
    except SyntaxError:
        return False
    open("_r.py", "w").write(text)
    c = subprocess.run(["python3.13", "_r.py"], capture_output=True, text=True, timeout=20)
    if c.returncode != 0:
        return False
    r = subprocess.run([P, "ir", "_r.py", "-o", "/dev/null"], capture_output=True, text=True, timeout=120)
    return needle in r.stderr


def block_end(lines, i):
    ind = len(lines[i]) - len(lines[i].lstrip())
    j = i + 1
    while j < len(lines) and (lines[j].strip() == "" or len(lines[j]) - len(lines[j].lstrip()) > ind):
        j += 1
    return j


assert interesting(src), "not interesting to begin with"
changed = True
while changed:
    changed = False
    i = len(src) - 1
    while i >= 0:
        if src[i].strip() == "":
            i -= 1; continue
        j = block_end(src, i)
        cand = src[:i] + src[j:]
        if interesting(cand):
            src = cand; changed = True
        elif j > i + 1:
            # try removing just the header and dedenting its body one level
            body = [l[4:] if l.startswith(" " * 4) else l for l in src[i + 1:j]]
            ind = len(src[i]) - len(src[i].lstrip())
            body = [(" " * ind + l.lstrip()) if (len(l) - len(l.lstrip())) < ind else l for l in body]
            cand = src[:i] + body + src[j:]
            if interesting(cand):
                src = cand; changed = True
        i -= 1
open(path.replace(".py", ".min.py"), "w").write("\n".join(src) + "\n")
print("\n".join(src))
