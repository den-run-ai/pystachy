# error: cannot infer the type of field 'value'
def retain(value):
    return value


def replacement(value: int) -> str:
    return str(value)


class Holder:
    def __init__(self, value, retain):
        self.value = retain(value)


print(Holder(1, replacement).value)
