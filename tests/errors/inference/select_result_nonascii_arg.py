# error: repair() returns both tuple[str,list[str]] and str (each function has one return type): its parameter 'logging' chooses which, and this call gives it no literal: pass a literal or annotate the result
# An argument computed from a str of other than ASCII characters is no selector's literal: len("é")
# is 1, where the compiler holds two UTF-8 bytes.
def repair(s: str, logging: bool = False):
    if logging:
        return s, ["log"]
    return s


print(repair("a", len("é") == 1))
