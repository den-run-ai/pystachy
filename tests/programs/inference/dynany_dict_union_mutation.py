# pystachy: dynamic-any
# A dict merge checks the source size after each insertion, including the last.
from typing import Any

source: Any = {}
armed: list[int] = [-1]


class Key:
    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return self.value

    def __eq__(self, other: Any) -> bool:
        mode = armed[0]
        armed[0] = -1
        if mode == 0:
            source.clear()
        elif mode == 1:
            source[3] = 40
        elif mode == 2:
            del source[2]
        elif mode == 3:
            source[2] = 31
        elif mode == 4:
            source.clear()
            source[8] = 80
            source[9] = 90
        elif mode == 5:
            source.clear()
            raise ValueError("callback")
        return isinstance(other, Key) and self.value == other.value


for operation in range(3):
    for mode in range(6):
        left: Any = {Key(1): 10}
        source = {Key(1): 20, 2: 30}
        armed[0] = mode
        print(operation, mode)
        try:
            if operation == 0:
                result = left | source
                print(list(result.values()))
            elif operation == 1:
                left |= source
            else:
                left.update(source)
        except RuntimeError as error:
            print(type(error).__name__, str(error))
        except ValueError as error:
            print(type(error).__name__, str(error))
        print(list(left.values()), list(source.values()))

# Mutation after the last source entry is checked too.
for operation in range(2):
    left = {Key(1): 10}
    source = {Key(1): 20}
    armed[0] = 0
    try:
        if operation == 0:
            result = left | source
        else:
            left |= source
    except RuntimeError as error:
        print("last", operation, str(error))

# Self-update does not run comparisons or raise a mutation error.
source = {Key(1): 20}
armed[0] = 0
source |= source
source.update(source)
print(len(source), armed[0])
