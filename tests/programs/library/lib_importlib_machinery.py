# importlib.machinery's suffix lists: a source module is a .py file. The lists of bytecode and
# extension suffixes are CPython's own (tests/deviations/lib_importlib_machinery_suffixes.py);
# mypyc's fallback for an empty one (mypyc/common.py) gives a name CPython accepts too.
import importlib.machinery
from importlib.machinery import SOURCE_SUFFIXES, all_suffixes

print(SOURCE_SUFFIXES, importlib.machinery.SOURCE_SUFFIXES == [".py"])
print(all_suffixes()[0], ".py" in importlib.machinery.all_suffixes())
_EXT_SUFFIXES = importlib.machinery.EXTENSION_SUFFIXES
EXT_SUFFIX = _EXT_SUFFIXES[0] if _EXT_SUFFIXES else ".so"
print(EXT_SUFFIX.endswith(".so"))
print(len(all_suffixes()) == len(SOURCE_SUFFIXES) + len(importlib.machinery.BYTECODE_SUFFIXES) + len(_EXT_SUFFIXES))
