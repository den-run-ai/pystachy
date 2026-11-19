"""Garbage collector interface: CPython's C module gc, for Pystachy's collector.

Pystachy loads this file for import gc, where CPython imports its C module
(Modules/gcmodule.c, whose docstrings and error these are; lib/provenance.md).

CPython's gc controls its collector of reference cycles, which works beside reference counts.
Here one tracing collector reclaims all memory (docs/internals.md), and the module is what of
that interface means something for it (lib/compatibility.md#gc):

- collect() runs a collection now. It returns 0: nothing counts the unreachable objects.
- enable(), disable() and isenabled(), set_threshold() and get_threshold(), set_debug() and
  get_debug() keep the settings that CPython keeps and report them, and freeze() and
  unfreeze() are calls without effect. None of them changes when the collector runs: it
  reclaims what CPython's reference counts would, which CPython's settings do not stop.

Its other names (get_objects(), get_referrers(), get_stats(), get_count(), get_freeze_count(),
callbacks, garbage and the like) describe CPython's object graph and generations, and are not
here.
"""

__all__ = ["collect", "enable", "disable", "isenabled", "set_debug", "get_debug",
           "set_threshold", "get_threshold", "freeze", "unfreeze",
           "DEBUG_STATS", "DEBUG_COLLECTABLE", "DEBUG_UNCOLLECTABLE", "DEBUG_SAVEALL", "DEBUG_LEAK"]

DEBUG_STATS = 1
DEBUG_COLLECTABLE = 2
DEBUG_UNCOLLECTABLE = 4
DEBUG_SAVEALL = 32
DEBUG_LEAK = 38

# the settings, as CPython 3.13 starts with them
_enabled = True
_debug = 0
_threshold: list[int] = [2000, 10, 10]


def enable() -> None:
    """Enable automatic garbage collection."""
    global _enabled
    _enabled = True


def disable() -> None:
    """Disable automatic garbage collection."""
    global _enabled
    _enabled = False


def isenabled() -> bool:
    """Returns true if automatic garbage collection is enabled."""
    return _enabled


def collect(generation: int = 2) -> int:
    """Run the garbage collector.

    With no arguments, run a full collection.  The optional argument
    may be an integer specifying which generation to collect.  A ValueError
    is raised if the generation number is invalid.

    The number of unreachable objects is returned.
    """
    if generation < 0 or generation > 2:
        raise ValueError("invalid generation")
    __pys_gc_collect()
    return 0


# set_debug() and set_threshold() take their arguments by position only, as CPython's C functions
# do, which raise TypeError where a call passes a keyword or another number of arguments: so do
# these, as the call runs (a positional-only parameter would make a keyword a compile-time error).
def set_debug(*args: int, **kwargs) -> None:
    """Set the garbage collection debugging flags."""
    global _debug
    if len(kwargs) > 0:
        raise TypeError("gc.set_debug() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("gc.set_debug() takes exactly one argument (%d given)" % len(args))
    _debug = args[0]


def get_debug() -> int:
    """Get the garbage collection debugging flags."""
    return _debug


def set_threshold(*args: int | None, **kwargs) -> None:
    """Set the collection thresholds (the collection frequency).

    Setting 'threshold0' to zero disables collection.
    """
    if len(kwargs) > 0:
        raise TypeError("set_threshold() takes no keyword arguments")
    if len(args) < 1 or len(args) > 3:
        raise TypeError("gc.set_threshold requires 1 to 3 arguments")
    # threshold0, then threshold1 and threshold2 where given: one that is not stays what it is,
    # as CPython's optional arguments leave it. Each is an int (CPython converts them all
    # before it sets one), and None is CPython's TypeError.
    given: list[int] = []
    for a in args:
        if a is None:
            raise TypeError("'NoneType' object cannot be interpreted as an integer")
        given.append(a)
    for i in range(len(given)):
        _threshold[i] = given[i]


def get_threshold() -> tuple[int, int, int]:
    """Return the current collection thresholds."""
    return (_threshold[0], _threshold[1], _threshold[2])


def freeze() -> None:
    """Freeze all current tracked objects and ignore them for future collections."""


def unfreeze() -> None:
    """Unfreeze all objects in the permanent generation."""
