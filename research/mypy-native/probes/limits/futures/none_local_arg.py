# A template whose parameter is None for a call tests it with "is None"; where the argument is a
# local that only holds None (not the constant), the branch for another type is compiled too
def wait_for(timeout) -> None:
    if timeout is None:
        raise RuntimeError("for ever")
    elif timeout > 0:
        print("sleep", timeout)


def use(timeout=None) -> None:
    if timeout is None:
        wait_timeout = None
    else:
        wait_timeout = timeout - 1.0
    try:
        wait_for(wait_timeout)
    except RuntimeError as e:
        print("RuntimeError:", e)


use()
use(2.0)
