class Value:
    def __init__(self, n: int):
        self.n = n

    def __repr__(self):
        return f"Value({self.n})"

    def __str__(self):
        return str(self.n)

    def __len__(self):
        return self.n

    def __bool__(self):
        return self.n != 0

for n in [0, 2]:
    v = Value(n)
    print(str(v), repr(v), len(v), bool(v), [v])

class One:
    def __len__(self):
        return True

print(len(One()), One().__len__())
