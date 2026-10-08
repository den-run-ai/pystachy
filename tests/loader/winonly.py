import sys
print("winonly loaded")
if sys.platform != "win32":
    raise ImportError("winonly needs Windows")


def f() -> int:
    return 1
