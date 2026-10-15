# error: expected bool, got int
class Value:
    def __bool__(self):
        return 1

print(bool(Value()))
