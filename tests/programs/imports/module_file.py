# A module's __file__ is the absolute path of its source file: the program's own, an imported
# module's and a package's (its __init__.py), read in module code, in functions and as m.__file__.
import os

import mods.file_of
from mods import file_of as helper

HERE = os.path.dirname(__file__)


def beside(name: str) -> str:
    return os.path.join(os.path.dirname(__file__), name)


print(os.path.basename(__file__), os.path.isabs(__file__), os.path.exists(__file__))
print(os.path.basename(HERE), os.path.basename(beside("x.txt")), beside("module_file.py") == __file__)
print(helper.own(), helper.folder(), os.path.basename(mods.file_of.__file__), os.path.isabs(helper.__file__))
print(os.path.basename(mods.__file__), os.path.dirname(mods.__file__) == os.path.dirname(helper.__file__))
with open(__file__) as f:
    print(f.readline().strip())
names = [os.path.basename(p) for p in [__file__, helper.__file__]]
print(names, f"{os.path.basename(__file__)!r}")
