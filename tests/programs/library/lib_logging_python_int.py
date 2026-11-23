# pystachy: python-int
# a log message's %d, %x, %o and %.2f of an int past 64 bits, which a module that opts in to
# promoting ints passes: lib/_pystachy_percent.py formats each value of object by what it holds,
# all of its digits, as CPython's % does; %c and a * width beside them
import logging
import sys

logging.basicConfig(stream=sys.stdout, format="%(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("t")
big = 2 ** 70
log.info("%d %x %o %5d", big, big, big, 3)
log.info("%c|%*d|%.2f", 65, 4, 7, big)
print("done")
