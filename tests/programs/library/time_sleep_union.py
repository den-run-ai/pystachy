# time.sleep() of an int | float: the call of each member's value (a float's, an int's) gives None,
# so splitting the union has no values to join. It emitted an LLVM `phi void`, which opt rejects
# (#1358). Both members sleep here: a float for a millisecond, an int for no time.
import time


def nap(t: float, cap: int) -> None:
    timeout = t
    if timeout > cap:
        timeout = cap  # (an int: timeout is an int | float)
    r = time.sleep(timeout)
    print("slept", timeout, r)


nap(0.001, 1)
nap(5.0, 0)
