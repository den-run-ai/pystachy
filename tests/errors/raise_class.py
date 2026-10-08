# error: 'E' is not an exception class: only the builtin exceptions can be raised (there is no inheritance)
class E:
    pass


raise E()
