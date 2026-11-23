# A selector is a value too: the instance reads the argument it was given.
def report(s: str, verbose: bool = False):
    if verbose:
        return s, verbose, [len(s)]
    print("quiet", verbose, str(verbose))
    return s


def pad(s: str, width: int = 0):
    if width:
        return s.ljust(width), width
    return [s, str(width)]


print(report("x"), report("y", verbose=True))
print(pad("a"), pad("b", 3), pad("c", width=0))
