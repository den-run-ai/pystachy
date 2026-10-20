# error: V.__pow__() takes 1 positional argument but 2 were given
class V:
    def __pow__(self, *, exponent=2):
        return exponent


print(V() ** 3)
