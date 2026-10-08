# error: unsupported decorator @register
def register(f):
    print("registering")
    return f


@register
def old(x):
    return x
