# Copying a deque preserves the exact subclass and maxlen (#1741).
# Its native iterator reads storage, not a subclass's len/getitem overrides.
from collections import deque
from copy import copy


class Queue(deque):
    def __len__(self) -> int:
        return 99

    def __getitem__(self, i: int) -> int:
        return -99


class DeepQueue(Queue):
    pass


for original in [deque([1, 2], 3), Queue([1, 2], 3), DeepQueue([1, 2], 3), Queue([1, 2])]:
    copied = original.copy()
    print(type(original).__name__, type(copied).__name__, len(copied), copied.maxlen)
    print(repr(copied), copied is original, [x for x in copied])
    copied.append(3)
    print([x for x in original], [x for x in copied])
    again = copy(original)
    print(type(again).__name__, again.maxlen, [x for x in again])
