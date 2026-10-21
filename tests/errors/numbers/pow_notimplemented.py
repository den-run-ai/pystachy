# error: the builtin 'NotImplemented' cannot be used as a value
class V:
    def __pow__(self, exponent):
        return NotImplemented


print(V() ** 2)
