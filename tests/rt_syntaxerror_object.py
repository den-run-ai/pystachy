# A SyntaxError's message as CPython's traceback shows it: str(e) is str(msg), then msg's truth,
# then str(msg) again for "SyntaxError: " + str(msg), which keeps its ": " for an empty string
class Msg:
    def __str__(self) -> str:
        print("str")
        return ""

    def __bool__(self) -> bool:
        print("bool")
        return True


raise SyntaxError(Msg())
