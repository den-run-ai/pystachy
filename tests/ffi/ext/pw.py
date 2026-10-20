"""Work for CPython's process pools (pwclient.py, aioclient.py): run by CPython as it is, or
compiled by `pystachy ext` into pw.abi3.so. Each process that imports the module runs its code,
with a runtime and heap of its own: count() counts that process's calls. Nothing prints, so that
the workers' output cannot interleave with the client's."""
import os
import sys
from ffi import export

_calls = 0


@export
def count() -> int:
    global _calls
    _calls += 1
    return _calls


@export
def pid() -> int:
    return os.getpid()


@export
def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@export
def squares(n: int) -> str:
    return ",".join([str(i * i) for i in range(n)])


@export
def check(n: int) -> int:
    if n < 0:
        raise ValueError(f"negative: {n}")
    return n


class _Missing(LookupError):
    pass


@export
def lookup(k: str) -> int:
    raise _Missing("no " + k)


@export
def bye(code: int) -> None:
    sys.exit(code)


@export
def killed() -> int:
    # a shell kills this process (SIGKILL, as the OOM killer does) while the call waits for it: the
    # call never returns
    return os.system("kill -9 $PPID")
