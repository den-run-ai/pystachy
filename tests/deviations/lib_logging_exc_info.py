# pystachy: dynamic-any
# logging.makeLogRecord() of a dict whose exc_info is not None raises NotImplementedError: the
# exception of a (type, value, traceback) cannot be taken out of an Any value here (an exception
# class cannot become one). CPython keeps the value, and its formatter later formats it (for this
# str, a TypeError). The dicts of SocketHandler and QueueHandler have exc_info None and the
# traceback's text in exc_text, which work (tests/programs/library/lib_logging_make_record.py)
import logging
from typing import Any

d: dict[str, Any] = {"msg": "m", "args": (), "exc_info": "not None"}
try:
    logging.makeLogRecord(d)
except NotImplementedError as e:
    print("NotImplementedError", e)
