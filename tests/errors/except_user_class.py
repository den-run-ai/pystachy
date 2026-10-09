# error: catching classes that do not inherit from BaseException is not allowed
class Problem:
    def __init__(self, why: str):
        self.why = why


try:
    print("x")
except Problem:
    pass
