"""Extract, format and print information about Python stack traces.

Pystachy's subset implementation of CPython 3.13.16's Lib/traceback.py. Pystachy keeps no
tracebacks and has no frames (lib/compatibility.md#traceback), so each exception formats as CPython
formats one whose __traceback__ is None: its exception-only lines, after those of its cause
(raise ... from), and each stack is empty. Its uncaught-exception report shows the same last line.
"""
import sys

__all__ = ['extract_stack', 'extract_tb', 'format_exception',
           'format_exception_only', 'format_list', 'format_stack',
           'format_tb', 'print_exc', 'format_exc', 'print_exception',
           'print_list', 'print_stack', 'print_tb', 'clear_frames']


def print_list(extracted_list: list[str], file=None) -> None:
    """Print the list of tuples as returned by extract_tb() or
    extract_stack() as a formatted stack trace to the given file."""
    # (the lists are empty: no frames)
    _print_lines(format_list(extracted_list), file)


def format_list(extracted_list: list[str]) -> list[str]:
    """Format a list of FrameSummary objects for printing (here, an empty one)."""
    return list(extracted_list)


def print_tb(tb, limit=None, file=None) -> None:
    """Print up to 'limit' stack trace entries from the traceback 'tb' (here, none)."""
    print_list(extract_tb(tb, limit=limit), file=file)


def format_tb(tb, limit=None) -> list[str]:
    """A shorthand for 'format_list(extract_tb(tb, limit))' (here, an empty list)."""
    return format_list(extract_tb(tb, limit=limit))


def extract_tb(tb, limit=None) -> list[str]:
    """Return the stack trace entries of the traceback 'tb': none, as Pystachy keeps none."""
    return []


def _exc_type_str(value) -> str:
    # TracebackException.exc_type_str: the class's qualified name, after its module's name but
    # for __main__'s and builtins' classes
    stype = type(value).__qualname__
    smod = type(value).__module__
    if smod != "__main__" and smod != "builtins":
        stype = smod + "." + stype
    return stype


def _safe_str(value) -> str:
    # _safe_string(value, 'exception')
    try:
        return str(value)
    except BaseException:
        return "<exception str() failed>"


def _final_line(value) -> str:
    # _format_final_exc_line(): "Type: message", or "Type" where the message is empty
    if value is None:
        return "NoneType: None\n"
    valuestr = _safe_str(value)
    if not valuestr:
        return _exc_type_str(value) + "\n"
    return _exc_type_str(value) + ": " + valuestr + "\n"


def _as_exc(value) -> BaseException:
    # an exception as a BaseException, which has __cause__ also where its class is one of the
    # program's (whose objects have only their class's fields): the exception that catching it gives
    try:
        raise value
    except BaseException as e:
        return e


def _format_chain(value, chain: bool) -> list[str]:
    # TracebackException.format() of an exception without a traceback: the lines of its causes
    # (as raise ... from gives them), first the earliest, then its own exception-only line; a
    # cause already shown ends the chain, as CPython's _seen does
    if value is None:
        return [_final_line(None)]
    lines: list[str] = []
    if chain:
        causes: list[BaseException] = []
        c = _as_exc(value).__cause__
        while c is not None and c is not value and not any(x is c for x in causes):
            causes.append(c)
            c = c.__cause__
        for i in range(len(causes) - 1, -1, -1):
            lines.append(_final_line(causes[i]))
            lines.append("\nThe above exception was the direct cause of the following exception:\n\n")
    lines.append(_final_line(value))
    return lines


def _format(exc, value, chain: bool) -> list[str]:
    # _parse_value_tb() and TracebackException.format(): the lines of value, where it is given
    # (the legacy (type, value, tb) form), else of exc (the one argument), which is None or an
    # exception; a traceback is always None here
    if value is not None:
        return _format_chain(value, chain)
    return _format_exc_arg(exc, chain)


def _format_exc_arg(exc, chain: bool) -> list[str]:
    if exc is None:
        return [_final_line(None)]
    if not isinstance(exc, BaseException):
        raise TypeError(f"Exception expected for value, {type(exc).__name__} found")
    return _format_chain(exc, chain)


def print_exception(exc, /, value=None, tb=None, limit=None, file=None, chain=True) -> None:
    """Print exception up to 'limit' stack trace entries from 'tb' to 'file'.

    Pystachy keeps no tracebacks: this prints the exception-only lines of the exception and of
    its causes."""
    _print_lines(_format(exc, value, chain), file)


def _print_lines(lines: list[str], file) -> None:
    # (to file, or to sys.stderr where it is None: a variable has one type)
    if file is None:
        for line in lines:
            print(line, file=sys.stderr, end="")
    else:
        for line in lines:
            print(line, file=file, end="")


def format_exception(exc, /, value=None, tb=None, limit=None, chain=True) -> list[str]:
    """Format a stack trace and the exception information.

    The arguments have the same meaning as the corresponding arguments
    to print_exception().  The return value is a list of strings, each
    ending in a newline and some containing internal newlines.  When
    these lines are concatenated and printed, exactly the same text is
    printed as does print_exception().
    """
    return _format(exc, value, chain)


def format_exception_only(exc, /, value=None) -> list[str]:
    """Format the exception part of a traceback.

    The return value is a list of strings, each ending in a newline.
    """
    if value is not None:
        return [_final_line(value)]
    return [_final_line(exc)]


def print_exc(limit=None, file=None, chain=True) -> None:
    """Shorthand for 'print_exception(sys.exception(), limit=limit, file=file, chain=chain)'."""
    print_exception(sys.exception(), limit=limit, file=file, chain=chain)


def format_exc(limit=None, chain=True) -> str:
    """Like print_exc() but return a string."""
    return "".join(format_exception(sys.exception(), limit=limit, chain=chain))


def print_stack(f=None, limit=None, file=None) -> None:
    """Print a stack trace from its invocation point (here, none: Pystachy has no frames)."""
    print_list(extract_stack(f, limit=limit), file=file)


def format_stack(f=None, limit=None) -> list[str]:
    """Shorthand for 'format_list(extract_stack(f, limit))' (here, an empty list)."""
    return format_list(extract_stack(f, limit=limit))


def extract_stack(f=None, limit=None) -> list[str]:
    """Extract the raw traceback from the current stack frame: none, as Pystachy has no frames."""
    return []


def clear_frames(tb) -> None:
    "Clear all references to local variables in the frames of a traceback (here, none)."
    return None
