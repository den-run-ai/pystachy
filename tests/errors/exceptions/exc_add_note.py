# error: E has no method add_note() of its own, and BaseException.add_note() is not supported
class E(Exception):
    pass


e = E("x")
e.add_note("note")
