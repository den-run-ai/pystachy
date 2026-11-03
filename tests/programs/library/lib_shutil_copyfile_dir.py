# shutil.copyfile() of a directory onto an existing file: CPython's open(src, 'rb') raises
# IsADirectoryError before the destination is opened, so the destination keeps its contents.
# The same holds for shutil.copy(), and for a source that does not exist.
import os
import shutil
import tempfile

base = tempfile.mkdtemp()
src = os.path.join(base, "srcdir")
dst = os.path.join(base, "dst.txt")
os.mkdir(src)
with open(dst, "w") as f:
    f.write("keep me\n")
for name in ["copyfile", "copy"]:
    try:
        if name == "copyfile":
            shutil.copyfile(src, dst)
        else:
            shutil.copy(src, dst)
        print(name, "copied")
    except IsADirectoryError as e:
        print(name, "IsADirectoryError:", str(e).replace(base, "BASE"))
    with open(dst) as f:
        print(name, repr(f.read()))
try:
    shutil.copyfile(os.path.join(base, "missing"), dst)
except FileNotFoundError as e:
    print("missing FileNotFoundError:", str(e).replace(base, "BASE"))
with open(dst) as f:
    print("missing", repr(f.read()))
os.remove(dst)
os.rmdir(src)
os.rmdir(base)
print(os.path.exists(base))
