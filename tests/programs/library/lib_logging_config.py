# lib/logging: basicConfig() of a stream, a level and a format, records of the module's
# functions and of child loggers, and the levels that a logger's effective level lets through
import logging
import sys

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger("app")
log.debug("debug %d", 1)
log.info("info %s and %r", "x", "y")
log.warning("warn")
child = logging.getLogger("app.child")
child.error("child error %.2f", 3.14159)
print(child.parent is log, child.getEffectiveLevel(), logging.getLevelName(logging.INFO))
log.setLevel(logging.WARNING)
log.info("hidden")
log.critical("crit %s", 5)
print(log.isEnabledFor(logging.ERROR), log.isEnabledFor(logging.INFO), child.isEnabledFor(logging.INFO))
logging.info("root info %d%%", 50)
logging.log(logging.ERROR, "logged at %s", "ERROR")
logging.basicConfig(format="ignored: %(message)s")
logging.warning("still the first format")
logging.basicConfig(force=True, stream=sys.stdout, format="forced %(levelno)s %(message)s", style="%")
logging.error("after force")
logging.basicConfig(force=True, stream=sys.stdout, format="{name}|{message}", style="{", level="INFO")
logging.info("brace style")
logging.getLogger("app").warning("propagated")
try:
    logging.basicConfig(style="?")
except ValueError as e:
    print("ValueError:", e)
