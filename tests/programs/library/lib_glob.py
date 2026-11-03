import glob
import os
import tempfile

base = tempfile.mkdtemp()
for d in ["a", "a/b", "c", ".hid"]:
    os.mkdir(os.path.join(base, d))
for f in ["x.py", "y.txt", "a/z.py", "a/b/w.py", ".h.py", "c/q.py", ".hid/r.py"]:
    with open(os.path.join(base, f), "w") as fh:
        fh.write(f)


def rel(paths: list[str]) -> list[str]:
    return sorted([p[len(base) + 1:] if p.startswith(base + "/") else p for p in paths])


print(rel(glob.glob(os.path.join(base, "*.py"))))
print(sorted(glob.glob("*.py", root_dir=base)), sorted(glob.glob("*", root_dir=base)))
print(sorted(glob.glob("**/*.py", root_dir=base, recursive=True)))
print(sorted(glob.glob("**", root_dir=base, recursive=True)))
print(sorted(glob.glob("**/", root_dir=base, recursive=True)))
print(sorted(glob.glob("*/*.py", root_dir=base)), sorted(glob.glob("?/", root_dir=base)))
print(sorted(glob.glob("*.py", root_dir=base, include_hidden=True)), sorted(glob.glob(".*", root_dir=base)))
print(sorted(glob.glob("a/[bz]*", root_dir=base)), glob.glob("nope*", root_dir=base), glob.glob("x.py", root_dir=base))
print(sorted(glob.iglob("**/*.py", root_dir=base, recursive=True)) == sorted(glob.glob("**/*.py", root_dir=base, recursive=True)))
print(glob.escape("a*b?[c]"), glob.has_magic("a*"), glob.has_magic("ab"))
print(sorted(os.listdir(base)), os.path.isdir(os.path.join(base, "a")), os.path.isfile(os.path.join(base, "a")))
print(os.path.isfile(os.path.join(base, "x.py")), os.path.lexists(os.path.join(base, "nope")), os.path.islink(base))
os.rename(os.path.join(base, "y.txt"), os.path.join(base, "y2.txt"))
os.replace(os.path.join(base, "y2.txt"), os.path.join(base, "x.py"))
print(sorted(glob.glob("*", root_dir=base)), os.path.samefile(base, os.path.join(base, "a", "..")))
try:
    os.listdir(os.path.join(base, "nope"))
except FileNotFoundError as e:
    print("FileNotFoundError", str(e).startswith("[Errno 2] No such file or directory: "))
try:
    os.rename(os.path.join(base, "nope"), os.path.join(base, "nope2"))
except FileNotFoundError as e:
    print("FileNotFoundError", str(e).endswith("nope2'"))
for f in ["x.py", "a/z.py", "a/b/w.py", ".h.py", "c/q.py", ".hid/r.py"]:
    os.unlink(os.path.join(base, f))
for d in ["a/b", "a", "c", ".hid"]:
    os.rmdir(os.path.join(base, d))
os.rmdir(base)
print(os.path.exists(base))
