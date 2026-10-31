# Uncaught rendering runs user code while the throwing frame is still active.
# Delayed depth publication must happen before that callback, even without a
# source-level caller handler that could restore or otherwise expose the depth.
import sys


class Error(Exception):
    def __str__(self) -> str:
        try:
            sys.setrecursionlimit(3)
        except RecursionError:
            return "depth retained"
        return "depth lost"


def cold(n: int) -> int:
    if n < 0:
        raise Error()
    return n


cold(-1)
