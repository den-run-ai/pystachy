# (tests/errors/library/platform_flag_store.py: a module whose tests of _WIN are decided at compile time)
import sys

_WIN = sys.platform == "win32"
if _WIN:
    import nt
