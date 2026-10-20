# error: platform_flag_rebound.py:11: error: module 'nt' is not supported: it is not a builtin module
# A module-level name decides its tests only where the module assigns it a test of the platform
# once and nothing else binds it: here a second assignment makes 'if _MS_WINDOWS:' a test that runs,
# and so its import must resolve
import sys

_MS_WINDOWS = sys.platform == "win32"
if len(sys.argv) > 5:
    _MS_WINDOWS = True
if _MS_WINDOWS:
    import nt
