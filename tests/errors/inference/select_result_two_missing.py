# error: shape() returns both list[int] and tuple[int,int] (each function has one return type): its parameters 'wrap' and 'pair' choose which, and this call gives them no literals: pass literals or annotate the result
# Two selectors given variables: the message names both.
def shape(n: int, wrap=False, pair=False):
    if wrap:
        return [n]
    if pair:
        return (n, n)
    return n


def main(w: bool, p: bool) -> None:
    print(shape(1, w, p))


main(False, True)
