# shutil.rmtree() as CPython 3.13 runs it on Linux (_rmtree_safe_fd, through directory
# descriptors): a tree of files, subdirectories and links is removed without following its links
# (the directory and file they point to survive), and a link, a dangling link, a file, a missing
# path and "" raise CPython's errors, a link's being an OSError of no errno; ignore_errors passes
# over each, and leaves what it could not remove
import os
import shutil
import tempfile

b = tempfile.mkdtemp()


def p(*parts: str) -> str:
    return os.path.join(b, *parts)


def link(target: str, name: str) -> None:
    # (a symbolic link, made by ln: Pystachy has no os.symlink())
    if os.system("ln -s " + target + " " + name) != 0:
        print("ln failed")


def show(label: str, path: str, ignore: bool) -> None:
    try:
        shutil.rmtree(path, ignore_errors=ignore)
        print(label, "removed" if not os.path.lexists(path) else "kept")
    except OSError as e:
        print(label, type(e).__name__, str(e).replace(b, "B"))


os.mkdir(p("outside"))
with open(p("outside", "keep.txt"), "w") as f:
    f.write("kept\n")
os.mkdir(p("t"))
os.mkdir(p("t", "sub"))
os.mkdir(p("t", "sub", "deeper"))
os.mkdir(p("t", "empty"))
for name in [p("t", "a.txt"), p("t", "sub", "b.txt"), p("t", "sub", "deeper", "c.txt")]:
    with open(name, "w") as f:
        f.write(name[-5:])
link(p("outside"), p("t", "link_to_dir"))
link(p("outside", "keep.txt"), p("t", "sub", "link_to_file"))
link(p("nowhere"), p("t", "dangling"))
show("tree", p("t"), False)
print(sorted(os.listdir(p("outside"))), open(p("outside", "keep.txt")).read(), end="")
link(p("outside"), p("ld"))
link(p("outside", "keep.txt"), p("lf"))
link(p("nowhere"), p("dangling"))
with open(p("f"), "w") as f:
    f.write("f")
for ignore in [False, True]:
    for name in ["ld", "lf", "dangling", "f", "missing"]:
        show(name + (" ignored" if ignore else ""), p(name), ignore)
show("empty path", "", False)
show("trailing slash", p("outside") + "/", False)
print(sorted(os.listdir(b)))
shutil.rmtree(b)
print(os.path.exists(b))
