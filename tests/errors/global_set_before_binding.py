# error: expected int, got str
def setg() -> None:
    global G
    G = 2


setg()
G = str(G) + "!"
print(G)
