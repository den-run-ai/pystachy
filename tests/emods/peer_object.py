import emods.peer_helper


class C(object):
    "peer_helper has rebound object (to 7) when this class statement runs"

    def __init__(self) -> None:
        self.v = 1


object = 5
