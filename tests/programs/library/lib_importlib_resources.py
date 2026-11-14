# importlib.resources.files(): the directory of a package or module that the program imports, a
# pathlib.Path, with CPython's errors for names that the program has no module of.
import os
from importlib import resources
from importlib.resources import files

import respkg
import respkg.mod
import respkg.sub

root = files("respkg")
print(type(root).__name__, root.name, root.is_dir(), root.is_absolute())
print(str(root).endswith("/resource_packages/respkg"), os.path.isdir(str(root)))
print((root / "data" / "hello.txt").read_text(), end="")
print(root.joinpath("data", "hello.txt").is_file(), (root / "missing.txt").exists())
print(sorted([p.name for p in (root / "data").iterdir()]))

# a subpackage and a submodule: the directories that hold their files
print(files("respkg.sub").name, files("respkg.mod").name)
print(files("respkg.sub") == root / "sub", files("respkg.mod") == root)

# mypy's use (mypy/util.py): the path of a directory beside the package's modules, as text
TYPESHED_DIR = str(resources.files("respkg") / "typeshed")
print(TYPESHED_DIR.endswith("/respkg/typeshed"), TYPESHED_DIR == os.path.join(str(root), "typeshed"))

# a package's own code names itself
print(respkg.NAME, respkg.data_dir().name, respkg.mod.where() == root, respkg.sub.note(), end="")

for anchor in ["nope", "respkg.nope", "nope.deeper", "respkg.mod.deeper", "", ".relative"]:
    try:
        files(anchor)
    except ModuleNotFoundError as e:
        print(type(e).__name__, e)
    except (ValueError, TypeError) as e:
        print(type(e).__name__, e)
