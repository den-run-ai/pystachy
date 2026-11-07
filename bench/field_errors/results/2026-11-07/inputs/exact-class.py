class Exact:
    def __init__(self, ready: bool) -> None:
        if ready:
            self.value = 7

def read(obj: Exact) -> int:
    return obj.value
print(read(Exact(True)))
