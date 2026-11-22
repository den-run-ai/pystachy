# Two selectors: an instance for each pair of literals. Where one literal decides every return, the
# other may be any value: shape(1, True, p) never tests pair.
def shape(n: int, wrap=False, pair=False):
    if wrap:
        return [n]
    if pair:
        return (n, n)
    return n


def main(p: bool) -> None:
    print(shape(1, True, p))


print(shape(1), shape(2, True), shape(3, pair=True), shape(4, True, True))
main(False)
