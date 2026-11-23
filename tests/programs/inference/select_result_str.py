# A str selector compared with == and with in: its literal decides the tests, a default too.
def opener(name: str, mode: str = "r"):
    if mode == "rb":
        return name.encode()
    if mode in ("r", "rt"):
        return name
    return len(name)


print(opener("ab"), opener("ab", "rb"), opener("ab", mode="rt"), opener("ab", "w"))
print(opener("xyz", mode="wb") + 1)
