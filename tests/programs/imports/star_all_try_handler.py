# A star import takes the __all__ that a module's top-level try statement binds (#1513), also
# where an except clause would rebind it: no statement of the body can raise, so that clause
# never runs, and only "a" is imported.
b = "main's b"
from loader.alltry_handler import *

print(a, b)
