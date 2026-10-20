# error: object has no attribute 'z'
class P:
    def __init__(self, x: int):
        self.x = x
print(P(1).z)
