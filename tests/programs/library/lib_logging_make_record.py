# pystachy: dynamic-any
# logging.makeLogRecord() sets a record's own attributes from the dict's keys that name them, as
# CPython's update of the record's __dict__ does (exc_text, stack_info, thread, process, ...), so
# the formatter shows them; other keys are attributes too
import logging
from typing import Any

d: dict[str, Any] = {"msg": "message", "args": (), "exc_text": "saved traceback", "stack_info": "saved stack",
                     "exc_info": None, "thread": 5, "threadName": "T5", "process": 7, "processName": "P7",
                     "taskName": "task", "custom": "extra value"}
r = logging.makeLogRecord(d)
print(repr(logging.Formatter().format(r)))
f = logging.Formatter("%(thread)d %(threadName)s %(process)d %(processName)s %(taskName)s %(custom)s %(message)s")
print(repr(f.format(r)))
print(r.exc_text, r.stack_info, r.exc_info, r.thread, r.process)
