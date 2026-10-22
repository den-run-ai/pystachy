# Empty-container inference types a template call before emitting the real call.
def identity(value):
    return value


values = {}
values.setdefault(0, []).append(identity(3))
print(values)
