# A template __eq__ that calls a function of an imported module that does not compile: the tuple
# search compiles that function where its call of __eq__ for a pair of classes first reaches it,
# so the pair declines rather than making the program a compile error, as before the search
# dispatched on classes (#409)
from search_unsupported import bad


class A:
    def __eq__(self, other: object) -> bool:
        return bad()


class B:
    pass


def search(x: A | B, y: A | B) -> bool:
    return x in (y,)


print(search(B(), B()))
