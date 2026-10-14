# A named closure sees the closest enclosing import, even when a module-level import
# uses the same alias. Parameters, assignments, own imports and globals still shadow it.
import closureimports.first as g
from closureimports.first import value as choice


def modules() -> list[int]:
    import closureimports.second as g

    def inner() -> int:
        return g.A

    def own_import() -> int:
        import closureimports.first as g

        def nested() -> int:
            return g.A

        return nested()

    def deep() -> int:
        def nested() -> int:
            return g.A

        return nested()

    def parameter(g: int) -> int:
        def nested() -> int:
            return g

        return nested()

    def assigned() -> int:
        g = 4

        def nested() -> int:
            return g

        return nested()

    def global_import() -> int:
        global g
        return g.A

    return [inner(), own_import(), deep(), parameter(3), assigned(), global_import()]


def without_global() -> int:
    import closureimports.second as localmod

    def inner() -> int:
        return localmod.A

    return inner()


def functions() -> list[int]:
    from closureimports.second import value as choice

    def inner() -> int:
        return choice()

    def own_import() -> int:
        from closureimports.first import value as choice
        return choice()

    def global_import() -> int:
        global choice
        return choice()

    return [inner(), own_import(), global_import()]


def variables() -> int:
    from closureimports.second import A

    def inner() -> int:
        return A

    A += 1
    return inner()


def classes() -> int:
    from closureimports.second import Box as box

    def inner() -> box:
        return box(7)

    return inner().value


def variable_outer() -> int:
    g = 99

    def inner() -> int:
        import closureimports.second as g
        return g.A

    return g + inner()


def branches(flag: bool) -> int:
    if flag:
        import closureimports.second as local
    else:
        import closureimports.second as local

    def inner() -> int:
        return local.A

    return inner()


print(modules(), without_global(), functions(), variables(), classes(), variable_outer(), g.factory()(), branches(True), branches(False))
