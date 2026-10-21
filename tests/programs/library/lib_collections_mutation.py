# CPython's deque comparison callbacks, including its match-before-state-check distinction.
# Reference: Modules/_collectionsmodule.c, CPython 3.13.16 cbc944f4bc59639a444dd971c737788ba2283a91.
# These exercise typed items with matching/nonmatching callbacks, append/clear/rotate,
# and same-length replacement/reverse (which do not change CPython's mutation state).
from collections import deque


class Item:
    def __init__(self, value: int, action: int = 0) -> None:
        self.value = value
        self.action = action

    def __eq__(self, other: "Item") -> bool:
        global active
        action = self.action
        self.action = 0
        if action == 1:
            active.append(Item(99))
        elif action == 2:
            active[1] = Item(99)
        elif action == 3:
            active.clear()
        elif action == 4:
            active.reverse()
        elif action == 5:
            active.rotate(0)
        elif action == 6:
            active *= 1
        return self.value == other.value

    def __repr__(self) -> str:
        return str(self.value)


empty: list[Item] = []
active = deque(empty)
for action in range(1, 7):
    for value in [1, 2]:
        for operation in ["contains", "count", "index", "remove"]:
            active = deque([Item(1, action), Item(2)])
            target = Item(value)
            try:
                if operation == "contains":
                    print(action, value, operation, target in active, active)
                elif operation == "count":
                    print(action, value, operation, active.count(target), active)
                elif operation == "index":
                    print(action, value, operation, active.index(target), active)
                else:
                    active.remove(target)
                    print(action, value, operation, active)
            except RuntimeError as error:
                print(action, value, operation, "RuntimeError", str(error), active)
            except IndexError as error:
                print(action, value, operation, "IndexError", str(error), active)
            except ValueError as error:
                print(action, value, operation, "ValueError", str(error), active)
