# pystachy: dynamic-any
# Merely boxing an unsupported operand pair must not reject the program. The
# selected typed/supported method still runs; absent methods retain identity.
from typing import Any


class Holder:
    def __init__(self) -> None:
        self.items = [1]

    def __eq__(self, other: "Holder") -> bool:
        print("holder body")
        box = [other]
        return len(box[0].items) == len(self.items)


class Peer:
    def __init__(self) -> None:
        self.items = ["x"]


class Winner:
    def __eq__(self, other: Any) -> bool:
        print("winner eq")
        return True

    def __gt__(self, other: Any) -> bool:
        print("winner gt")
        return True


class Plain:
    pass


def fail() -> Any:
    print("operand")
    raise ValueError("operand failed first")


holder: Any = Holder()
same: Any = Holder()
peer: Any = Peer()
winner: Any = Winner()
plain: Any = Plain()
other: Any = Plain()
print(holder == same)
print(winner == holder, winner != holder)
print(plain == winner, plain < winner)
print(plain == plain, plain == other, plain != other, plain == peer)
print(plain in [plain], holder in [holder])
try:
    print(plain < other)
except TypeError:
    print("no ordering method")
try:
    print(holder == fail())
except ValueError as error:
    print(error)
finally:
    print("operand cleanup")
if plain is other:
    print(holder == peer)
print("untaken comparison")
