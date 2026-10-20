# A module global that a function gives an int, and module code then a str: int | str.
def setg() -> None:
    global G
    G = 2


setg()
G = str(G) + "!"
print(G)
