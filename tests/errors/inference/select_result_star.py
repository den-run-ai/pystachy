# error: repair() returns both tuple[str,list[str]] and str (each function has one return type): its parameter 'logging' chooses which, and this call gives it no literal
# A *args argument gives the selector a tuple's item, not a literal.
def repair(s: str, logging: bool = False):
    if logging:
        return s, ["log"]
    return s


args = (" a ", True)
print(repair(*args))
