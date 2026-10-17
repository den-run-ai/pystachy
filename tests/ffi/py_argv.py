# sys.argv as CPython decodes it: an undecodable byte becomes a lone surrogate (surrogateescape)
import sys
from pyobj import import_module

argv = import_module("sys").attr("argv")
s = str(import_module("json").attr("dumps").call([argv]))
print(len(argv), len(sys.argv), s[s.find(", ") + 2 :])
