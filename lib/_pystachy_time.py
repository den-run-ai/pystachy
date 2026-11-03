"""time.strftime() of a time.localtime() or time.gmtime(), for Pystachy's library.

Pystachy's builtin time module has no localtime(), gmtime() or strftime() (docs/language/modules.md).
strftime_at() is the one combination that logging's Formatter.formatTime() needs, through the C
library's localtime_r(), gmtime_r() and strftime() (runtime.c's pys_strftime_at), with CPython
3.13's results on Linux: CPython's time module calls the same functions. Programs do not import
this module.
"""

__all__ = ["strftime_at"]


def strftime_at(format: str, secs: float, utc: bool = False) -> str:
    """time.strftime(format, time.gmtime(secs) if utc else time.localtime(secs))."""
    return __pys_strftime_at(format, secs, 1 if utc else 0)
