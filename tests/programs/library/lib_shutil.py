import os
import posixpath
import shutil
import tempfile

base = tempfile.mkdtemp()
src = os.path.join(base, "src.txt")
with open(src, "w") as f:
    f.write("payload\n")
dst = shutil.copyfile(src, os.path.join(base, "dst.txt"))
print(posixpath.basename(dst), open(dst).read().strip())
os.mkdir(os.path.join(base, "sub"))
c = shutil.copy(src, os.path.join(base, "sub"))
print(c[len(base) + 1:], open(c).read().strip())
try:
    shutil.copyfile(src, src)
except shutil.SameFileError as e:
    print("SameFileError", str(e).endswith("are the same file"))
try:
    shutil.copyfile(os.path.join(base, "nope"), dst)
except FileNotFoundError as e:
    print("FileNotFoundError", str(e).startswith("[Errno 2] No such file or directory: "))
m = shutil.move(dst, os.path.join(base, "sub"))
print(m[len(base) + 1:], os.path.exists(dst))
try:
    shutil.move(os.path.join(base, "sub", "dst.txt"), os.path.join(base, "sub"))
except shutil.Error as e:
    print("Error", "already exists" in str(e))
m2 = shutil.move(os.path.join(base, "sub", "dst.txt"), os.path.join(base, "moved.txt"))
print(m2[len(base) + 1:], sorted(os.listdir(base)), sorted(os.listdir(os.path.join(base, "sub"))))
os.mkdir(os.path.join(base, "sub", "deep"))
with open(os.path.join(base, "sub", "deep", "f"), "w") as f:
    f.write("x")
shutil.rmtree(os.path.join(base, "sub"))
print(sorted(os.listdir(base)))
try:
    shutil.rmtree(os.path.join(base, "sub"))
except FileNotFoundError as e:
    print("FileNotFoundError", str(e).startswith("[Errno 2] No such file or directory: "))
shutil.rmtree(os.path.join(base, "sub"), ignore_errors=True)
try:
    shutil.rmtree(src)
except NotADirectoryError as e:
    print("NotADirectoryError", str(e).startswith("[Errno 20] Not a directory: "))
shutil.rmtree(base)
print(os.path.exists(base), issubclass(shutil.SameFileError, shutil.Error), issubclass(shutil.Error, OSError))
