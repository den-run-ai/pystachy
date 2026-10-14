# error: 'local' is read in outer() where Pystachy cannot tell that the import in it that binds 'local' has run
def outer() -> int:
    def inner() -> int:
        return local.V

    print(inner())
    import eload.fine2 as local
    return inner()


print(outer())
