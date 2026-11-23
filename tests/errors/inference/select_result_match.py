# error: opener() returns both bytes and str (each function has one return type) (compiling opener(str, str) for the call at tests/errors/inference/select_result_match.py:12)
# A match statement tests a copy of its subject, which no literal decides: an if statement on the
# parameter does.
def opener(name: str, mode: str = "r"):
    match mode:
        case "rb":
            return name.encode()
        case _:
            return name


print(opener("a"), opener("b", "rb"))
