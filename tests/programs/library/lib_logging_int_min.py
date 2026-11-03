# A log message's %d of the least int of the range, -2**63, read at run time: the record's
# message is formatted (lib/_pystachy_percent.py) and reaches the handler's stream, as in CPython,
# rather than failing in formatting and reporting a logging error
import logging
import sys

logging.basicConfig(stream=sys.stdout, format="%(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger("t")
lo = int("-9223372036854775808")
log.info("%d", lo)
log.info("%x %o %i", lo, lo, lo)
log.warning("min %+d, max %d", lo, int("9223372036854775807"))
print("done")
