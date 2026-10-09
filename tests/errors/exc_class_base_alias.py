# error: class inheritance is not supported (only an exception class may have a base, which names a builtin exception class or an exception class of the program)
VE = ValueError


class E(VE):
    pass
