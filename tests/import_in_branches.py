# An import in a function binds a local of it, which a read after the import has surely run
# finds bound: after both branches of an if, a with block or an if True block.
def both(verbose: bool) -> int:
    if verbose:
        import loader.helper
    else:
        import loader.helper
    return loader.helper.V


def inwith() -> int:
    with open("/dev/null") as f:
        import loader.helper
    return loader.helper.V + 1


def always() -> int:
    if True:
        import loader.helper
    return loader.helper.V + 2


print(both(True), both(False), inwith(), always())
