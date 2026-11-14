# A class attribute read where a later class body runs has the value its class holds then.
class Limits:
    depth = 1
    names = ["a"]


Limits.depth = 5
Limits.names = ["b", "c"]


class Walker:
    depth = Limits.depth
    names = Limits.names

    def __init__(self) -> None:
        self.start = Limits.depth


Limits.depth = 6
print(Walker.depth, Walker.names, Walker().start, Walker.names is Limits.names)
