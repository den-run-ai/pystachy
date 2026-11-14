# pystachy: dynamic-any
import logging
import sys
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("app")
log.info("user=%s n=%d ratio=%.2f", "ann", 3, 0.5)
log.warning("items %r", [1, "two"])
