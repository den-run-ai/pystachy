# error: select.select() timeout must be int, float or None; narrow optional values before the call
import select


def wait(timeout: float | None) -> None:
    select.select([], [], [], timeout)


wait(None)
