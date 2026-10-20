from typing import Optional


class V:
    def __init__(self):
        self.x = 0

    def __add__(self, o: "V") -> "V":
        return V()


a: Optional[V] = None
a += V()
