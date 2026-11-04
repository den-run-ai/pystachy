# error: flag class Sparse is not supported: unnamed bits with a custom _iter_member_()
from enum import Flag


class Base(Flag):
    @classmethod
    def _iter_member_(cls, value):
        yield None


class Sparse(Base):
    A = 1
    AC = 5


print(list(Sparse.AC))
