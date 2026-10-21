# error: name 'sys' is not defined
print("start")
if sys.platform == "win32":
    print("win")
else:
    print("posix")
import sys
