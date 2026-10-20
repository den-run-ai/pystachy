# error: a generator expression that reads 'i' is not supported where main() may bind it again, or it may be unbound, before the generator runs (a generator expression reads it then)
def main() -> None:
    gs = []
    for i in range(3):
        gs.append(c * i for c in [1, 2])
    print([list(g) for g in gs])


main()
