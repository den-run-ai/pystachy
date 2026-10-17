import reent


def make():
    return lambda i: reent.inner(i) * 2


class Box:
    def __getitem__(self, i):
        return reent.inner(i) + 1
