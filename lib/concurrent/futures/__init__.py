# Copyright 2009 Brian Quinlan. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""Execute computations asynchronously using threads or processes."""

# Pystachy port of CPython 3.13.16's Lib/concurrent/futures/__init__.py (lib/provenance.md):
# ThreadPoolExecutor runs each call on the one thread a Pystachy program has (thread.py), and
# there is no ProcessPoolExecutor. Each change is marked "Pystachy port".

__author__ = 'Brian Quinlan (brian@sweetapp.com)'

from concurrent.futures._base import (FIRST_COMPLETED,
                                      FIRST_EXCEPTION,
                                      ALL_COMPLETED,
                                      CancelledError,
                                      TimeoutError,
                                      InvalidStateError,
                                      BrokenExecutor,
                                      Future,
                                      Executor,
                                      wait,
                                      as_completed)
# Pystachy port: imported here, where CPython's module __getattr__() imports it at its first use
# (a module has no __getattr__() and __dir__()); no ProcessPoolExecutor, in __all__ either
from concurrent.futures.thread import ThreadPoolExecutor

__all__ = (
    'FIRST_COMPLETED',
    'FIRST_EXCEPTION',
    'ALL_COMPLETED',
    'CancelledError',
    'TimeoutError',
    'InvalidStateError',
    'BrokenExecutor',
    'Future',
    'Executor',
    'wait',
    'as_completed',
    'ThreadPoolExecutor',
)
