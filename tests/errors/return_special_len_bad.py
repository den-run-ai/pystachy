# error: __len__ must return int, and Value.__len__() returns str
class Value:
    def __len__(self):
        return "wrong"

print(len(Value()))
