import enum


class Kind(enum.IntEnum):
    A = 0


class Marker:
    pass


_marker = Marker()


class Holder:
    FIRST = Kind.A
    SECOND = Kind.A
    marker = _marker
