# A field annotated Callable holds a bound method or a lambda that takes any arguments.
from collections.abc import Callable


class P:
    def __init__(self, logging: bool) -> None:
        self.logger: list[str] = []
        self.log: Callable[[str], None]
        if logging:
            self.log = self._log
        else:
            self.log = lambda *args, **kwargs: None

    def _log(self, text: str) -> None:
        self.logger.append(text)


a = P(True)
b = P(False)
a.log("x")
b.log("y")
print(a.logger, b.logger)
