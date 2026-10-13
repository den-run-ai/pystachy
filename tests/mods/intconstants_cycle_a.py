def early() -> int:
    return VALUE


from . import intconstants_cycle_b
VALUE = 37


def late() -> int:
    return VALUE
