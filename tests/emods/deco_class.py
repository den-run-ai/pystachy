def tag(c):
    print("tagged", c.__name__)
    return c


@tag
class Thing:
    pass
