# error: cannot import name 'PureWindowsPath' from 'pathlib'
# Pystachy's pathlib has the POSIX classes (CPython prints c:\a)
from pathlib import PureWindowsPath

print(PureWindowsPath("c:/a"))
