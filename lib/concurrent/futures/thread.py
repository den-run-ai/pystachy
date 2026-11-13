# Copyright 2009 Brian Quinlan. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""Implements ThreadPoolExecutor."""

# Pystachy port of CPython 3.13.16's Lib/concurrent/futures/thread.py (lib/provenance.md). A
# Pystachy program runs one thread (docs/concurrency.md), which threading.Thread.start() cannot
# add to, so this executor has no worker threads: submit() runs the call on the calling thread,
# before it returns, and gives back a finished future. That is one of the schedules CPython's
# pool may take for calls that do not wait for each other, and the only one here. Each change is
# marked "Pystachy port".

__author__ = 'Brian Quinlan (brian@sweetapp.com)'

from concurrent.futures import _base
# Pystachy port: no itertools, queue, threading, types, weakref and os: there is no thread to
# name, feed through a queue, join or wake when its executor is collected, and no os.fork()


# Pystachy port: no _threads_queues, _shutdown, _global_shutdown_lock and _python_exit(), which
# join the worker threads as the interpreter exits, and no os.register_at_fork()

# Pystachy port: no _WorkItem and no _worker(): a work item holds a call for a worker thread to
# run later, with a future made before the call. Here submit() runs the call and makes the
# future from what it returned, which types the future (see _base.Future)


class BrokenThreadPool(_base.BrokenExecutor):
    """
    Raised when a worker thread in a ThreadPoolExecutor failed initializing.
    """


# Pystachy port: the count that names an executor's threads, which CPython's class attribute
# _counter = itertools.count().__next__ steps (a generator's method is not a value)
_counter = 0


class ThreadPoolExecutor(_base.Executor):

    # Pystachy port: no initializer and initargs, which CPython runs in each worker thread as it
    # starts (they would also make the class a template of their types, which no field of
    # another class could be annotated with); max_workers and thread_name_prefix are annotated
    def __init__(self, max_workers: int | None = None, thread_name_prefix: str = ''):
        """Initializes a new ThreadPoolExecutor instance.

        Args:
            max_workers: The maximum number of threads that can be used to
                execute the given calls.
            thread_name_prefix: An optional name prefix to give our threads.
        """
        global _counter
        if max_workers is None:
            # ThreadPoolExecutor is often used to:
            # * CPU bound task which releases GIL
            # * I/O bound task (which releases GIL, of course)
            #
            # We use process_cpu_count + 4 for both types of tasks.
            # But we limit it to 32 to avoid consuming surprisingly large resource
            # on many core machine.
            # Pystachy port: the subset's os has no process_cpu_count(); the count is taken as
            # unknown, for which CPython's (os.process_cpu_count() or 1) + 4 is 5
            max_workers = min(32, 1 + 4)
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")

        # Pystachy port: no _work_queue, _idle_semaphore, _threads, _broken, _shutdown_lock,
        # _initializer and _initargs (no worker threads); _max_workers is kept, and bounds
        # nothing
        self._max_workers = max_workers
        self._shutdown = False
        # Pystachy port: (the module's count, see _counter)
        if not thread_name_prefix:
            thread_name_prefix = "ThreadPoolExecutor-%d" % _counter
            _counter += 1
        self._thread_name_prefix = thread_name_prefix

    def submit(self, fn, /, *args, **kwargs):
        # Pystachy port: no _shutdown_lock and _global_shutdown_lock, no _broken (no initializer
        # fails) and no interpreter shutdown to refuse a call after
        if self._shutdown:
            raise RuntimeError('cannot schedule new futures after shutdown')

        # Pystachy port: _WorkItem.run()'s call, here and now, where CPython queues a work item
        # for a worker thread. What the call returns is kept in a tuple of one item, which is
        # the future's _result and whose type is the future's (see _base.Future), so the future
        # is made after the call: from that tuple, or from the None of a call that raised. It is
        # a Future[int] for a call that returns an int; the Future[None] named here is what the
        # tuple of a call that returns None leaves it to be. The future then takes the states
        # that _WorkItem.run() gives it
        result = None
        failure = None
        try:
            result = (fn(*args, **kwargs),)
        except BaseException as exc:
            failure = exc
        f = _base.Future[None]((result,))
        f._state = _base.RUNNING
        if failure is not None:
            f.set_exception(failure)
        else:
            f._state = _base.FINISHED
        return f

    def shutdown(self, wait=True, *, cancel_futures=False):
        # Pystachy port: no call is pending or running: there is no future to cancel, no worker
        # to wake and no thread to join
        self._shutdown = True
