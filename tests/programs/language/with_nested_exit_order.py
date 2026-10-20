# An exception from a function closes the caller's with files in reverse entry order.
import sys


def stop() -> None:
    sys.exit(0)


with open("/dev/stderr", "a") as outer:
    outer.write("outer\n")
    with open("/dev/stderr", "a") as inner:
        inner.write("inner\n")
        stop()
