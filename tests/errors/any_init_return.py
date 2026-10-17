# error: typing.Any is only supported
# Only parameters are inferred: __init__ keeps its existing return contract.
from typing import Any


class Holder:
    def __init__(self, value: Any) -> Any:
        self.value = value


print(Holder(1).value)
