class E(Exception):
    def __str__(self):
        raise RuntimeError("no str")


def boom():
    raise E()
