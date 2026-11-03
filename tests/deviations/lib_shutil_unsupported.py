# Documented deviation: shutil.rmtree() with onerror, onexc or dir_fd, and shutil.copyfile() of a
# symbolic link with follow_symlinks=False, raise NotImplementedError (lib/compatibility.md#shutil),
# where CPython calls the handler (here it has nothing to handle), removes the tree relative to the
# descriptor, and makes a link like the source
import os
import shutil
import tempfile

b = tempfile.mkdtemp()
d = os.path.join(b, "d")


def handler(func: object, path: str, exc: object) -> None:
    print("handler", path)


for how in ["onexc", "onerror", "dir_fd"]:
    os.mkdir(d)
    try:
        if how == "onexc":
            shutil.rmtree(d, onexc=handler)
        elif how == "onerror":
            shutil.rmtree(d, onerror=handler)
        else:
            shutil.rmtree(d, dir_fd=-100)  # (an absolute path: the descriptor is not used)
        print(how, "removed")
    except NotImplementedError as e:
        print(how, "NotImplementedError:", e)
    if os.path.exists(d):
        os.rmdir(d)
with open(os.path.join(b, "f"), "w") as f:
    f.write("x")
if os.system("ln -s f " + os.path.join(b, "lf")) != 0:
    print("ln failed")
try:
    shutil.copyfile(os.path.join(b, "lf"), os.path.join(b, "copy"), follow_symlinks=False)
    print("copyfile", os.path.islink(os.path.join(b, "copy")))
except NotImplementedError as e:
    print("copyfile NotImplementedError:", e)
shutil.rmtree(b)
print(os.path.exists(b))
