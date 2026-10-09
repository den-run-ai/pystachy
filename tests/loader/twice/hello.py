print("hello runs as", __name__)
N = [0]
COUNT = 1


def bump() -> int:
    N[0] += 1
    return N[0]
