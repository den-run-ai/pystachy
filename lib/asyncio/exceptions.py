"""asyncio exceptions."""


# Pystachy port: no TimeoutError, the builtin class that CPython's module names again (an alias
# of a builtin class is not supported): asyncio.TimeoutError is TimeoutError
__all__ = ('BrokenBarrierError',
           'CancelledError', 'InvalidStateError',
           'IncompleteReadError', 'LimitOverrunError',
           'SendfileNotAvailableError')


class CancelledError(BaseException):
    """The Future or Task was cancelled."""


class InvalidStateError(Exception):
    """The operation is not allowed in this state."""


class SendfileNotAvailableError(RuntimeError):
    """Sendfile syscall is not available.

    Raised if OS does not support sendfile syscall for given socket or
    file type.
    """


class IncompleteReadError(EOFError):
    """
    Incomplete read error. Attributes:

    - partial: read bytes string before the end of stream was reached
    - expected: total number of expected bytes (or None if unknown)
    """
    # Pystachy port: annotated parameters; no __reduce__ (no pickling)
    def __init__(self, partial: bytes, expected: int | None) -> None:
        r_expected = 'undefined' if expected is None else repr(expected)
        super().__init__(f'{len(partial)} bytes read on a total of '
                         f'{r_expected} expected bytes')
        self.partial = partial
        self.expected = expected


class LimitOverrunError(Exception):
    """Reached the buffer limit while looking for a separator.

    Attributes:
    - consumed: total number of to be consumed bytes.
    """
    # Pystachy port: annotated parameters; no __reduce__ (no pickling)
    def __init__(self, message: str, consumed: int) -> None:
        super().__init__(message)
        self.consumed = consumed


class BrokenBarrierError(RuntimeError):
    """Barrier is broken by barrier.abort() call."""


# Pystachy port: the exception that raising exc raises, as a value of type BaseException, which
# a Future keeps and a coroutine's throw() takes (an object of a class of the program is converted
# where it is raised and caught)
def _as_exception(exc) -> BaseException:
    try:
        raise exc
    except BaseException as e:
        return e
