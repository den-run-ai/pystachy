# error: cannot infer the type of field 'value'
def retain(value):
    return value


class Holder:
    def __init__(self, value):
        self.value = retain(value=value)


print(Holder(1).value)
