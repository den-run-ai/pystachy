# error: cannot compare Failed == Plain
# An exception class's object and an object of an ordinary class stay rejected: exceptions
# compare by rules of their own (CPython prints False)
class Failed(Exception):
    pass


class Plain:
    pass


print(Failed("x") == Plain())
