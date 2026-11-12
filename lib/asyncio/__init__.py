"""The asyncio package, tracking PEP 3156."""

# flake8: noqa

# Pystachy port: the event loop, futures, tasks, gather(), sleep(), TaskGroup, timeouts, Lock, Event
# and Queue; no coroutines, protocols, streams, subprocesses, threads, transports or the platforms'
# loops (lib/compatibility.md#asyncio)

# Pystachy port: the submodules first, which a star import does not bind in the package
from . import base_events, events, exceptions, futures, locks, runners, queues, tasks, taskgroups, timeouts

# This relies on each of the submodules having an __all__ variable.
from .base_events import *
from .events import *
from .exceptions import *
from .futures import *
from .locks import *
from .runners import *
from .queues import *
from .tasks import *
from .taskgroups import *
from .timeouts import *

__all__ = (base_events.__all__ +
           events.__all__ +
           exceptions.__all__ +
           futures.__all__ +
           locks.__all__ +
           runners.__all__ +
           queues.__all__ +
           tasks.__all__ +
           taskgroups.__all__ +
           timeouts.__all__)
