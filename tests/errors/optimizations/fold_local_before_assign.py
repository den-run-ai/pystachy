# error: local variable 'sys' is read before its first assignment
# A platform test on a local sys is not decided, and reads the local, not the module.
import sys


class Fake:
    def __init__(self, platform: str) -> None:
        self.platform = platform


def f() -> None:
    if sys.platform == "win32":
        print("win")
    else:
        print("posix")
    sys = Fake("x")
    print(sys.platform)


print("start")
f()
