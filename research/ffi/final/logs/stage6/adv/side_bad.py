import sys


class W:
    def write(self, s):
        raise ValueError("no writes")

    def flush(self):
        pass


def install():
    sys.stdout = W()


def restore():
    sys.stdout = sys.__stdout__


def noisy():
    print("py: no newline", end="")
    return 7
