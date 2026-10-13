class Box:
    def __init__(self, v):
        self.v = v

    def __call__(self, k: int):
        return self.v * k


def pick(flag):
    return Box(2) if flag else Box("ab")


print(pick(True)(3), pick(False)(2))
