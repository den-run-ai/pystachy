# lib/logging, CPython's logging (lib/compatibility.md#logging): loggers and their hierarchy,
# levels, the %, {} and $ styles of Formatter, extra, asctime, filters (objects and functions),
# exc_info, FileHandler, NullHandler and disable(); a raised exception's lines that only CPython
# has (its frames) are left out
import io
import logging
import os
import re
import tempfile


def make(fmt: str, style: str = "%") -> tuple[logging.Logger, io.StringIO]:
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(logging.Formatter(fmt, style=style))
    lg = logging.getLogger("t." + style + str(len(fmt)))
    lg.propagate = False
    lg.setLevel(logging.DEBUG)
    lg.addHandler(h)
    return lg, buf


lg, buf = make("%(levelname)-8s|%(name)s|%(message)s|%(levelno)d")
lg.debug("a=%d b=%s c=%r", 1, "two", 3.5)
lg.info("plain")
lg.warning("%5.1f%%", 99.44)
print(buf.getvalue(), end="")

lg2, buf2 = make("{levelname}:{name}:{message}", "{")
lg2.error("brace %s", "x")
print(buf2.getvalue(), end="")

lg3, buf3 = make("${levelname} ${message}", "$")
lg3.critical("dollar")
print(buf3.getvalue(), end="")

lg4, buf4 = make("%(message)s [%(user)s]")
lg4.info("with extra", extra={"user": "bob"})
print(buf4.getvalue(), end="")

lg5, buf5 = make("%(asctime)s %(message)s")
lg5.info("timed")
print(re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} timed\n", buf5.getvalue()) is not None)

lg6, buf6 = make("%(name)s:%(message)s")


class OnlyEven(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.msg.endswith("0") or record.msg.endswith("2")


def no_three(record: logging.LogRecord) -> bool:
    return "3" not in record.getMessage()


lg6.addFilter(OnlyEven())
for i in range(5):
    lg6.info("n%d" % i)
lg6.removeFilter(lg6.filters[0])
lg6.addFilter(no_three)
for i in range(5):
    lg6.info("m%d", i)
print(buf6.getvalue(), end="")

lg7, buf7 = make("%(levelname)s %(message)s")
try:
    raise ValueError("bad value")
except ValueError:
    lg7.exception("caught")
lines = buf7.getvalue().splitlines()
print(lines[0], "|", lines[-1])
empty: dict[str, int] = {}
try:
    empty["k"]
except KeyError as e:
    lg7.error("again", exc_info=e)
print(buf7.getvalue().splitlines()[-1])

parent = logging.getLogger("p")
child = logging.getLogger("p.c.d")
print(child.parent is parent, parent.getChild("c.d") is child, logging.getLogger("p.c").parent is parent)
parent.setLevel("ERROR")
print(child.getEffectiveLevel(), child.isEnabledFor(logging.WARNING), logging.getLevelName(40), logging.getLevelName("INFO"))
logging.addLevelName(25, "NOTICE")
print(logging.getLevelName(25), logging.getLevelName(26))
print(repr(child), repr(logging.getLogger()))

d = tempfile.mkdtemp()
path = os.path.join(d, "x.log")
fh = logging.FileHandler(path, mode="w")
fh.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
flog = logging.getLogger("file")
flog.propagate = False
flog.addHandler(fh)
flog.warning("to file %d", 7)
fh.close()
with open(path) as f:
    print(repr(f.read()))
os.remove(path)
os.rmdir(d)
nl = logging.getLogger("null")
nl.addHandler(logging.NullHandler())
nl.propagate = False
nl.error("nothing")
logging.disable(logging.CRITICAL)
lg.critical("disabled")
logging.disable(logging.NOTSET)
lg.critical("enabled")
print(buf.getvalue().splitlines()[-1])
print(logging.getLevelNamesMapping()["WARN"], len(logging.getHandlerNames()) >= 0)
