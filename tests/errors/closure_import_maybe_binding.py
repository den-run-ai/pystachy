# error: a def inside a function reads enclosing import 'local', which may be unbound (not supported)
def outer() -> int:
    try:
        import eload.fine2 as local
    except ValueError:
        pass

    def inner() -> int:
        return local.V

    return inner()


print(outer())
