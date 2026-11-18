# An optional import whose statements after the import bind __all__ (and call a function, where
# the program defines a subclass of ImportError) is decided as before (#1504): its __all__ is the
# module's, which a star import takes.
b = "main's b"
from loader.subimp.allmod import *

print(a, b)
