# A failed inner close replaces SystemExit and still closes the outer file.
import sys


def stop() -> None:
    with open("/dev/full", "w") as inner:
        inner.write("lost")
        sys.exit(0)


with open("/dev/stderr", "a") as outer:
    outer.write("outer\n")
    stop()
