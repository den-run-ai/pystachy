# error: property value needs a return annotation
# (a generator getter: an ordinary getter's type is inferred from its returns)
class C:
    @property
    def value(self):
        yield 1


print(list(C().value))
