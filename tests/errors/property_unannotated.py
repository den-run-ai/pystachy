# error: property value needs a return annotation
class C:
    @property
    def value(self):
        return 1


print(C().value)
