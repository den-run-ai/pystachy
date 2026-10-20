# error: expected str, got int
class Value:
    def __repr__(self):
        return 1

print(repr(Value()))
