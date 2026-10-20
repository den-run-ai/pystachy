class A:
    def __init__(self, others: list["A"]):
        if len(others) > 0:
            self = others[0]
        self.name = "a"


b = A([A([])])
print(b.name.upper())
