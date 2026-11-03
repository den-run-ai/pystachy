# lib/logging on sys.stderr: a logger without handlers reaches the last resort handler, the root's
# functions configure a StreamHandler of sys.stderr, and a message whose arguments do not fit its
# format is reported by Handler.handleError(), whose last line (this program's last on stderr) is
# CPython's; before it, Pystachy shows the record's unknown file where CPython shows frames
import logging

logging.getLogger("quiet").warning("last resort %s", "used")
logging.info("not shown")
logging.warning("root %d", 1)
logging.error("bad %d", "x")
print("stdout done")
