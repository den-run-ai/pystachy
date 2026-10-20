# error: __len__ must return int
class Value:
    def __len__(self):
        return None

print(len(Value()))
