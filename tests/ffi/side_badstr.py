class E(Exception):
    def __str__(self):
        raise RuntimeError("str() of E failed")


class F(Exception):
    def __str__(self):
        raise E()


def boom():
    raise E()


def boom2():
    raise F()
