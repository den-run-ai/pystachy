REG = {}


def fill() -> None:
    import emods.later_keys

    REG[emods.later_keys.KEY] = 1


print(REG)
fill()
print(REG)
