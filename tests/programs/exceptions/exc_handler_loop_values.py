# Values that reach an except clause from a loop whose call raised: the handler must see
# each variable as it was when that call raised, on the first read and inside the loop.
def skip_spaces(text: str, index: int) -> int:
    try:
        char = text[index]
        while char.isspace():
            index += 1
            char = text[index]
    except IndexError:
        pass
    return index


def last_before_missing(words: list[str], index: int) -> str:
    seen = "start"
    try:
        word = words[index]
        while word != "stop":
            seen = word
            index += 1
            word = words[index]
    except IndexError:
        pass
    return seen + " " + str(index)


print(skip_spaces("", -2), skip_spaces(" ", 0), skip_spaces("   ", 1), skip_spaces("a", 0))
print(last_before_missing([], 3))
print(last_before_missing(["a", "b"], 0))
print(last_before_missing(["a", "stop", "c"], 0))
