"""The caplog fixture for generated native tests.

Generated modules import this only when a test or fixture requests caplog, so other
suites do not compile logging. This is not pytest's implementation: one handler on the
root logger records from the fixture's setup to its teardown, where pytest starts a
new record list for each phase of a test.
"""

import logging


class LogCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class LevelContext:
    """`with caplog.at_level(level):` the levels as they were, where the block ends."""

    def __init__(self, capture: "LogCapture", kept: int) -> None:
        self.capture = capture
        self.kept = kept

    def __enter__(self) -> None:
        return None

    def __exit__(self, kind: object, value: object, traceback: object) -> None:
        self.capture.restore(self.kept)


class LogCapture:
    def __init__(self, handler: LogCaptureHandler) -> None:
        self.handler = handler
        self._levels: list[tuple[str, int, int]] = []

    @property
    def records(self) -> list[logging.LogRecord]:
        return self.handler.records

    @property
    def record_tuples(self) -> list[tuple[str, int, str]]:
        return [(str(record.name), int(record.levelno), record.getMessage()) for record in self.handler.records]

    @property
    def messages(self) -> list[str]:
        return [record.getMessage() for record in self.handler.records]

    @property
    def text(self) -> str:
        return "".join([f"{record.levelname:<8} {record.name}:{record.filename}:{record.lineno} "
                        f"{record.getMessage()}\n" for record in self.handler.records])

    def clear(self) -> None:
        self.handler.records.clear()

    def set_level(self, level: int | str, logger: str | None = None) -> None:
        """Set a logger's level and the handler's, until the test ends."""
        target = logging.getLogger(logger)
        self._levels.append((logger or "", int(target.level), int(self.handler.level)))
        target.setLevel(level)
        self.handler.setLevel(level)

    def at_level(self, level: int | str, logger: str | None = None) -> LevelContext:
        kept = len(self._levels)
        self.set_level(level, logger)
        return LevelContext(self, kept)

    def restore(self, kept: int) -> None:
        while len(self._levels) > kept:
            name, level, handler_level = self._levels.pop()
            logging.getLogger(name or None).setLevel(level)
            self.handler.setLevel(handler_level)


def caplog():
    handler = LogCaptureHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    capture = LogCapture(handler)
    yield capture
    capture.restore(0)
    root.removeHandler(handler)
