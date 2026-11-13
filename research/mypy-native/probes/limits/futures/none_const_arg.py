# the same with the constant None as the argument: compiles
def wait_for(timeout) -> None:
    if timeout is None:
        raise RuntimeError("for ever")
    elif timeout > 0:
        print("sleep", timeout)


def use(timeout=None) -> None:
    try:
        if timeout is None:
            wait_for(None)
        else:
            wait_for(timeout - 1.0)
    except RuntimeError as e:
        print("RuntimeError:", e)


use()
use(2.0)
