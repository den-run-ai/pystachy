# error: repair() returns both tuple[str,list[str]] and str (each function has one return type) (compiling repair(str, bool) for the call at tests/errors/inference/select_result_rebound.py:11)
# A parameter the body binds again is no selector: its argument decides nothing at compile time.
def repair(s: str, logging: bool = False):
    if s == "":
        logging = True
    if logging:
        return s, ["log"]
    return s


print(repair("a"))
