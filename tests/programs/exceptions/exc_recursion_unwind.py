# RecursionError follows ordinary finally/context-manager unwinding (#988).
# Every recursive call is finite even before native recursion guards exist.
import sys

entered = [0]
finished = [0]


def depth(n: int) -> int:
    entered[0] += 1
    try:
        if n == 0:
            return 0
        return 1 + depth(n - 1)
    finally:
        finished[0] += 1


def recover(n: int) -> int:
    if n == 0:
        try:
            return depth(100)
        except RecursionError:
            return depth(3)
    return 1 + recover(n - 1)


def user_error(n: int) -> None:
    if n == 0:
        raise ValueError("bounded")
    user_error(n - 1)


class Guard:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def __enter__(self) -> "Guard":
        self.events.append("enter")
        return self

    def __exit__(self, kind, error, traceback) -> bool:
        self.events.append("recursion" if kind is RecursionError else "other")
        return False


original = sys.getrecursionlimit()
sys.setrecursionlimit(60)
for attempt in range(4):
    entered[0] = 0
    finished[0] = 0
    events: list[str] = []
    try:
        with Guard(events):
            try:
                depth(100)
            finally:
                events.append("finally")
    except RecursionError:
        events.append("caught")
    print(entered[0] > 0, entered[0] == finished[0], events)
    print(depth(3), recover(10))
    try:
        user_error(10)
    except ValueError:
        print("user error", depth(3))
sys.setrecursionlimit(original)
