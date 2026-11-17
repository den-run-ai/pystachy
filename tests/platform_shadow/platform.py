# A program's own module named platform, found before lib/'s (the case's .path): it is no
# module of lib/, so lib/platform.py's private builtin is not defined in it.
def kernel() -> str:
    return __pys_uname(0)
