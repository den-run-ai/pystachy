class V:
    def __pow__(self, exponent):
        return NotImplemented


print(V() ** 2)
