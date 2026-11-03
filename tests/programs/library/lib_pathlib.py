import os
import tempfile
from pathlib import Path, PurePath, PurePosixPath

# pure paths
p = PurePath("/usr/lib/python3.13/os.py")
print(p, repr(p), p.name, p.stem, p.suffix, p.parent, p.anchor, p.root, p.drive)
print(p.parts, [str(x) for x in p.parents], len(p.parents), p.parents[0], p.is_absolute())
q = PurePosixPath("a/b.tar.gz")
print(q.suffixes, q.stem, q.with_name("c.txt"), q.with_suffix(".zip"), q.with_stem("d"), q.with_suffix(""))
print(PurePath("a", "b", "c"), PurePath("a") / "b" / "c", PurePath("/a", "/b"), PurePath(""), PurePath("."), PurePath("a//b/./c"))
print(PurePath("a").joinpath("b", "c"), PurePath("a/b") == PurePath("a//b"), PurePath("a") != PurePath("b"))
print(sorted([PurePath("b"), PurePath("a/c"), PurePath("a")]), hash(PurePath("x/y")) == hash(PurePath("x//y")))
print(PurePath("/a/b/c").relative_to("/a"), PurePath("a/b").relative_to("a/b"), PurePath("/a/b").is_relative_to("/a"))
print(PurePath("a/b").relative_to("a/c", walk_up=True), PurePath("/x").is_relative_to("/y"))
for bad in ["/a/c", "d"]:
    try:
        PurePath("/a/b").relative_to(bad)
    except ValueError as e:
        print("ValueError", e)
try:
    PurePath("a").with_name("")
except ValueError as e:
    print("ValueError", e)
try:
    PurePath("a/b").with_suffix("txt")
except ValueError as e:
    print("ValueError", e)
print(PurePath("a/b.py").match("*.py"), PurePath("a/b.py").match("a/*.py"), PurePath("a/b.py").match("/*.py"), PurePath("A.PY").match("*.py"))
print(isinstance(Path("x"), PurePath), isinstance(PurePath("x"), Path), type(Path("x")).__name__, type(PurePath("x")).__name__)
print(Path("a/~").expanduser() == Path("a/~"), Path("/x").expanduser(), Path("rel").absolute() == Path(os.getcwd()) / "rel")

# a directory tree
base = Path(tempfile.mkdtemp())
(base / "src" / "pkg").mkdir(parents=True)
(base / "src" / "pkg").mkdir(parents=True, exist_ok=True)
print((base / "src").is_dir(), (base / "src").is_file(), (base / "nope").exists())
n = (base / "src" / "main.py").write_text("print('hi')\n")
(base / "src" / "pkg" / "util.py").write_text("x = 1\n")
(base / "src" / "pkg" / "data.txt").write_text("data\n")
(base / "src" / ".hidden").write_text("")
print(n, (base / "src" / "main.py").read_text(), (base / "src" / "main.py").is_file())
print(sorted(x.name for x in (base / "src").iterdir()))
print(sorted(str(x.relative_to(base)) for x in base.glob("src/*.py")))
print(sorted(str(x.relative_to(base)) for x in base.rglob("*.py")))
print(sorted(str(x.relative_to(base)) for x in base.glob("**/")))
print(sorted(str(x.relative_to(base)) for x in (base / "src").glob("*")))
print(sorted(str(x.relative_to(base)) for x in base.glob("src/pkg/*.t?t")))
with (base / "src" / "pkg" / "data.txt").open() as f:
    print(f.read().strip())
t = (base / "src" / "main.py").rename(base / "src" / "app.py")
print(t.name, t.exists(), (base / "src" / "main.py").exists())
(base / "flag").touch()
print((base / "flag").exists())
(base / "flag").unlink()
(base / "flag").unlink(missing_ok=True)
try:
    (base / "flag").unlink()
except FileNotFoundError as e:
    print("FileNotFoundError", str(e).startswith("[Errno 2] No such file or directory: "))
try:
    (base / "src").mkdir()
except FileExistsError as e:
    print("FileExistsError", str(e).startswith("[Errno 17] File exists: "))
try:
    (base / "a" / "b").mkdir()
except FileNotFoundError as e:
    print("FileNotFoundError", str(e).startswith("[Errno 2] No such file or directory: "))
for victim in [base / "src" / "app.py", base / "src" / "pkg" / "util.py", base / "src" / "pkg" / "data.txt", base / "src" / ".hidden"]:
    victim.unlink()
(base / "src" / "pkg").rmdir()
(base / "src").rmdir()
base.rmdir()
print(base.exists())
