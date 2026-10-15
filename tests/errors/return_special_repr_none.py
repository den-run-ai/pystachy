# error: __repr__ must return str
class Value:
    def __repr__(self):
        pass

print(repr(Value()))
