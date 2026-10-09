# error: catching 'Problem' is not supported: only the builtin exceptions can be caught (there is no inheritance)
class Problem:
    def __init__(self, why: str):
        self.why = why


try:
    print("x")
except Problem:
    pass
