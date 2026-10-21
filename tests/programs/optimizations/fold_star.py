# A star import that binds os and sys to the modules this program imports too leaves the tests
# of the platform decided at compile time (the Windows branch is dropped, with its import).
import os
import sys
from loader.sameos import *

if os.name == "nt" or sys.platform == "win32":
    import winreg
print(X, os.name, sys.platform.startswith("win"))
