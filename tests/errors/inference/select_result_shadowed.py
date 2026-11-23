# error: repair() returns both tuple[str,list[str]] and str (each function has one return type): its parameter 'logging' chooses which, and this call gives it no literal: pass a literal or annotate the result (compiling repair(str, bool) for the call at tests/errors/inference/select_result_shadowed.py:13; compiling outer(str, bool) for the call at tests/errors/inference/select_result_shadowed.py:16)
# A comprehension's variable that shadows the calling instance's selector is no literal: outer's
# logging is False here, the comprehension's True.
def repair(s: str, logging: bool = False):
    if logging:
        return s, ["log"]
    return s


def outer(s: str, logging: bool = False):
    if logging:
        return [s]
    return str([repair(s, logging) for logging in [True]])


print(outer("c"), outer("d", True))
