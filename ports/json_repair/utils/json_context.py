# pystachy: dynamic-any
from types import TracebackType


# Pystachy port: private enum values are only compared and stacked.
class ContextValues:
    OBJECT_KEY = 1
    OBJECT_VALUE = 2
    ARRAY = 3


class _JsonContextEntry:
    __slots__ = ("context", "value")

    def __init__(self, context: "JsonContext", value: int) -> None:
        self.context = context
        self.value = value

    def __enter__(self) -> None:
        self.context.set(self.value)

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> bool:
        self.context.reset()
        return False


class JsonContext:
    def __init__(self) -> None:
        self.context: list[int] = []
        self.current: int | None = None
        self.empty: bool = True

    def enter(self, value: int) -> _JsonContextEntry:
        return _JsonContextEntry(self, value)

    def set(self, value: int) -> None:
        """
        Set a new context value.

        Args:
            value (ContextValues): The context value to be added.

        Returns:
            None
        """
        self.context.append(value)
        self.current = value
        self.empty = False

    def reset(self) -> None:
        """
        Remove the most recent context value.

        Returns:
            None
        """
        # Pystachy port: empty stacks are normal; avoid native exception unwinding.
        if self.context:
            self.context.pop()
        if self.context:
            self.current = self.context[-1]
        else:
            self.current = None
            self.empty = True

    def clear(self) -> None:
        """
        Remove all context values.

        Returns:
            None
        """
        self.context.clear()
        self.current = None
        self.empty = True
