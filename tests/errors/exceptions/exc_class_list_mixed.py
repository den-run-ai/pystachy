# error: objects of the exception classes S and N in one list are not supported: no class of the program is a base of both
class S(Exception):
    pass


class N(Exception):
    pass


for e in [S("s"), N("n")]:
    print(str(e), repr(e))
