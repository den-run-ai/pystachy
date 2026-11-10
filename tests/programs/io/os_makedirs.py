# os.makedirs(): the missing parents made first, mode and exist_ok by position or by name, and
# CPython's errors (the temporary directory's name is taken out of their messages)
import os
import tempfile

tmp = tempfile.mkdtemp()
deep = os.path.join(tmp, "a", "b", "c")
os.makedirs(deep)
print(os.path.isdir(deep), os.listdir(tmp), os.listdir(os.path.join(tmp, "a")))
os.makedirs(deep, exist_ok=True)
os.makedirs(os.path.join(tmp, "a"), 0o700, True)
os.makedirs(os.path.join(tmp, "m", "n"), mode=0o750)
os.makedirs(os.path.join(tmp, "m", "o"), mode=0o750, exist_ok=False)
os.makedirs(os.path.join(tmp, "t", "u") + "/")
os.makedirs(os.path.join(tmp, "d", "e", "."))
print(sorted(os.listdir(tmp)), sorted(os.listdir(os.path.join(tmp, "m"))), os.listdir(os.path.join(tmp, "t")), os.listdir(os.path.join(tmp, "d")))
for path in [deep, os.path.join(tmp, "a")]:
    try:
        os.makedirs(path)
    except FileExistsError as e:
        print("FileExistsError", str(e).replace(tmp, "TMP"))
with open(os.path.join(tmp, "file"), "w") as f:
    f.write("x")
try:
    os.makedirs(os.path.join(tmp, "file"), exist_ok=True)
except FileExistsError as e:
    print("FileExistsError", str(e).replace(tmp, "TMP"))
try:
    os.makedirs(os.path.join(tmp, "file", "under"))
except NotADirectoryError as e:
    print("NotADirectoryError", str(e).replace(tmp, "TMP"))
try:
    os.makedirs("")
except FileNotFoundError as e:
    print("FileNotFoundError", e)
missing = os.getenv("PYSTACHY_NO_SUCH_VAR")
try:
    os.makedirs(missing)
except TypeError as e:
    print("TypeError", e)
os.remove(os.path.join(tmp, "file"))
for sub in ["a/b/c", "a/b", "a", "m/n", "m/o", "m", "t/u", "t", "d/e", "d"]:
    os.rmdir(os.path.join(tmp, sub))
os.rmdir(tmp)
print(os.path.exists(tmp))
