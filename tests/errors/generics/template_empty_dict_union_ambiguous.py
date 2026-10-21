# error: returns an empty dict taken as dict[int,int]: give it a type first
# The same fallback explanation applies to an ambiguous dict result context.
def empty(n):
    return {}


result: dict[str, int] | dict[tuple[str, int], int] = empty(1)
