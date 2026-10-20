# error: syntax_global_dropped_branch.py:6: error: name 'x' is parameter and global
import sys

if sys.platform == "win32":
    def f(x: int) -> None:
        global x
print("ran")
