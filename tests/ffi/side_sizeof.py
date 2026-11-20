import sys


class Liar:
    # sys.getsizeof() adds this object's GC header and pre-header (32 bytes on CPython 3.12 and
    # 3.13) to what __sizeof__ returns, which stays below 2**63 so that it raises no OverflowError
    def __sizeof__(self):
        return 2 ** 63 - 65


def huge(o):
    return sys.getsizeof(o) > 2 ** 62
