# error: 'with' is supported for files only (with open(...) as f:), not C
class C:
    pass


with C() as c:
    pass
