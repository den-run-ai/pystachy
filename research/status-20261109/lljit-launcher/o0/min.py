def skip(text: str, index: int) -> int:
    try:
        char = text[index]
        while char.isspace():
            index += 1
            char = text[index]
    except IndexError:
        pass
    return index


print(skip("", -2), skip(" ", 0), skip("a", 0))
