# A class outside any hierarchy whose __init__ stores a class-template object into an annotated
# field stays a class template, as before: compiled only once used, so an unused one's other
# fields (self.y = [], whose type nothing gives) are never inferred, and the program runs.
from collections import deque


class A:
    x: deque[int]

    def __init__(self) -> None:
        self.x = deque()
        self.y = []


print("ok")
