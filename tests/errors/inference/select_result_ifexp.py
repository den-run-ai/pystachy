# error: expected tuple[str,list[str]], got str (compiling repair(str, bool) for the call at tests/errors/inference/select_result_ifexp.py:8)
# One return of a conditional expression whose arms have two types is no choice between returns:
# an if statement that returns each one is.
def repair(s: str, logging: bool = False):
    return (s, ["log"]) if logging else s


print(repair("a"), repair("b", True))
