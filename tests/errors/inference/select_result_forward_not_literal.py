# error: repair() returns both tuple[str,list[str]] and str (each function has one return type): its parameter 'logging' chooses which, and this call gives it no literal: pass a literal or annotate the result (compiling repair(str, bool) for the call at tests/errors/inference/select_result_forward_not_literal.py:11; compiling loads(str, bool) for the call at tests/errors/inference/select_result_forward_not_literal.py:15)
# Forwarding needs a literal at the outermost call too: main passes loads a variable, which
# loads passes on to repair.
def repair(s: str, logging: bool = False):
    if logging:
        return s, ["log"]
    return s


def loads(s: str, logging: bool = False):
    return repair(s, logging)


def main(flag: bool) -> None:
    print(loads("a", flag))


main(True)
