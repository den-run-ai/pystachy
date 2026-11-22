# error: repair() returns both tuple[str,list[str]] and str (each function has one return type): its parameter 'logging' chooses which, and this call gives it no literal: pass a literal or annotate the result
# A module's constant is a variable, not a literal.
DEBUG = True


def repair(s: str, logging: bool = False):
    if logging:
        return s, ["log"]
    return s


print(repair("a", DEBUG))
