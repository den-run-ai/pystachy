# A module that does not opt in to promoting ints, whose functions return and keep the *args tuple
# of a call, which holds the promoting ints they are given
# (tests/programs/numbers/python_int_varargs.py).


def fixed_pack(*args):
    return args


def fixed_keep(*key):
    d = {key: len(key)}
    return key in d, d
