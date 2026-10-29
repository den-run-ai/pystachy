# This module deliberately uses ordinary typed mode.
class Peer:
    def __init__(self, value: int) -> None:
        self.value = value


class Child(Peer):
    def __init__(self) -> None:
        super().__init__(7)
        self.tail = "tail"


def read(peer: Peer) -> int:
    return peer.value
