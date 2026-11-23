# error: repair() returns both tuple[str,list[str]] and str (each function has one return type): its parameter 'logging' chooses which, and this call gives it no literal: pass a literal or annotate the result (compiling repair(str, bool) for the call at tests/errors/inference/select_result_not_literal.py:11)
# A selector whose argument is a variable leaves both returns to run: one return type cannot hold
# them, and the message names the parameter whose literal would choose.
def repair(s: str, logging: bool = False):
    if logging:
        return s, ["log"]
    return s


def main(flag: bool) -> None:
    print(repair("a", flag))


main(True)
main(False)
