# error: repair() returns both tuple[str,list[str]] and str (each function has one return type): its parameter 'logging' chooses which, and this call gives it no literal
# A ** argument, also of a dict display, gives the selector a value, not a literal.
def repair(s: str, logging: bool = False):
    if logging:
        return s, ["log"]
    return s


print(repair("a", **{"logging": True}))
