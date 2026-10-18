# namedtuple() classes of an imported module, as the standard library writes them: a typename
# other than the variable's (unittest.util), the class's and its fields' docstrings assigned
# (pkgutil, sched, selectors), defaults, and functions that make objects of them
import collections
from collections import namedtuple

_Mismatch = namedtuple("Mismatch", "actual expected value")
ModuleInfo = namedtuple("ModuleInfo", "module_finder name ispkg")
ModuleInfo.__doc__ = "A namedtuple with minimal info about a module."
Event = namedtuple("Event", "time, priority, sequence, action, argument, kwargs")
Event.time.__doc__ = ("""Numeric type compatible with the return value of the
timefunc function passed to the constructor.""")
Event.priority.__doc__ = ("""Events scheduled for the same time will be executed
in the order of their priority.""")
SelectorKey = collections.namedtuple("SelectorKey", ["fileobj", "fd", "events", "data"])

SelectorKey.__doc__ = """SelectorKey(fileobj, fd, events, data)

    Object used to associate a file object to its backing
    file descriptor, selected event mask, and attached data.
"""
SelectorKey.fileobj.__doc__ = "File object registered."
SelectorKey.fd.__doc__ = "Underlying file descriptor."
Positions = collections.namedtuple("Positions", ["lineno", "end_lineno"], defaults=[0] * 2)
Key = SelectorKey


def mismatches(a, b):
    out = []
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            out.append(_Mismatch(a[i], b[i], i))
    return out


def schedule(t, action):
    return Event(t, 1, 0, action, (), {"k": t})
