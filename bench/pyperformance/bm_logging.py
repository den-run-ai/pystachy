"""
Script for testing the performance of logging simple messages.

Rationale for logging_silent by Antoine Pitrou:

"The performance of silent logging calls is actually important for all
applications which have debug() calls in their critical paths.  This is
quite common in network and/or distributed programming where you want to
allow logging many events for diagnosis of unexpected runtime issues
(because many unexpected conditions can appear), but with those logs
disabled by default for performance and readability reasons."

https://mail.python.org/pipermail/speed/2017-May/000576.html
"""

# Python imports
import io
import logging

# Pystachy port: use the upstream clocks with the deterministic runner.
import sys
import time

TIMED: list[float] = []

# A simple format for parametered logging
FORMAT = 'important: %s'
MESSAGE = 'some important information to be logged'


def truncate_stream(stream):
    stream.seek(0)
    stream.truncate()


def bench_silent(loops, logger, stream):
    truncate_stream(stream)

    # micro-optimization: use fast local variables
    m = MESSAGE
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: pyperf's clock.

    for _ in range_it:
        # repeat 10 times
        logger.debug(m)
        logger.debug(m)
        logger.debug(m)
        logger.debug(m)
        logger.debug(m)
        logger.debug(m)
        logger.debug(m)
        logger.debug(m)
        logger.debug(m)
        logger.debug(m)

    dt = time.perf_counter() - t0  # Pystachy port: pyperf's clock.

    if len(stream.getvalue()) != 0:
        raise ValueError("stream is expected to be empty")

    TIMED.append(dt)  # Pystachy port: retain each timed interval.


def bench_simple_output(loops, logger, stream):
    truncate_stream(stream)

    # micro-optimization: use fast local variables
    m = MESSAGE
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: pyperf's clock.

    for _ in range_it:
        # repeat 10 times
        logger.warning(m)
        logger.warning(m)
        logger.warning(m)
        logger.warning(m)
        logger.warning(m)
        logger.warning(m)
        logger.warning(m)
        logger.warning(m)
        logger.warning(m)
        logger.warning(m)

    dt = time.perf_counter() - t0  # Pystachy port: pyperf's clock.

    lines = stream.getvalue().splitlines()
    if len(lines) != loops * 10:
        raise ValueError("wrong number of lines")

    TIMED.append(dt)  # Pystachy port: retain each timed interval.


def bench_formatted_output(loops, logger, stream):
    truncate_stream(stream)

    # micro-optimization: use fast local variables
    fmt = FORMAT
    msg = MESSAGE
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: pyperf's clock.

    for _ in range_it:
        # repeat 10 times
        logger.warning(fmt, msg)
        logger.warning(fmt, msg)
        logger.warning(fmt, msg)
        logger.warning(fmt, msg)
        logger.warning(fmt, msg)
        logger.warning(fmt, msg)
        logger.warning(fmt, msg)
        logger.warning(fmt, msg)
        logger.warning(fmt, msg)
        logger.warning(fmt, msg)

    dt = time.perf_counter() - t0  # Pystachy port: pyperf's clock.

    lines = stream.getvalue().splitlines()
    if len(lines) != loops * 10:
        raise ValueError("wrong number of lines")

    TIMED.append(dt)  # Pystachy port: retain each timed interval.


# Pystachy port: a deterministic main replaces pyperf.Runner and its dispatch table.
if __name__ == "__main__":
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 32
    stream = io.StringIO()
    handler = logging.StreamHandler(stream=stream)
    logger = logging.getLogger("benchlogger")
    logger.propagate = False
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

    bench_silent(loops, logger, stream)
    assert stream.getvalue() == ""
    bench_simple_output(loops, logger, stream)
    assert stream.getvalue() == (MESSAGE + "\n") * (10 * loops)
    bench_formatted_output(loops, logger, stream)
    assert stream.getvalue() == ((FORMAT % MESSAGE) + "\n") * (10 * loops)
    print("seconds", sum(TIMED), file=sys.stderr)
    print("logging", loops, len(stream.getvalue()))
