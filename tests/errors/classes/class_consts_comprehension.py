# error: class attribute 'ADD' of 'Op' used in a class-body default is not supported
# (past its first iterable a comprehension does not read the class scope: CPython raises NameError)
class Op:
    ADD = 0
    codes: list[int] = [ADD for _ in range(2)]


print(Op.codes)
