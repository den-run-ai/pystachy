# error: 'C' object does not support the context manager protocol
class C:
    pass


with C() as c:
    pass
