# error: class attribute 'ADD' of 'Op' used in a class-body default is not supported
# (a lambda's body does not read the class scope: CPython's call raises NameError)
class Op:
    ADD = 0
    got: int = (lambda: ADD)()


print(Op.got)
