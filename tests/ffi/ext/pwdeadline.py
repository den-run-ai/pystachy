"""A deadline for a client of CPython's process pools (pwclient.py, aioclient.py). A timeout bounds
one wait, but a hung worker can still hold the client for ever: in ProcessPoolExecutor.__exit__(),
which waits for its calls, or in a join or an await without a timeout. Past the deadline, a timer
thread kills the client's child processes, reaps them and ends the client with status 3, whatever
its main thread is waiting for."""
import multiprocessing
import os
import sys
import threading


def start(seconds: float) -> None:
    def expire() -> None:
        try:
            children = multiprocessing.active_children()
            for p in children:
                p.kill()
            for p in children:
                p.join(10)
            print(f"deadline: the client ran past {seconds} s; killed and reaped {len(children)} child processes", file=sys.stderr, flush=True)
            sys.stdout.flush()
        finally:
            os._exit(3)

    t = threading.Timer(seconds, expire)
    t.daemon = True
    t.start()
