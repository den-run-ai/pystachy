# error: V.__ipow__() takes 1 positional argument but 2 were given
class V:
    def __ipow__(self, *, exponent=2):
        return self


value = V()
value **= 3
