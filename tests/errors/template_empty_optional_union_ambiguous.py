# error: returns an empty list taken as list[int]: give it a type first
# None does not disambiguate two list layouts or hide the fallback explanation.
def empty(n):
    return []


result: list[str] | list[float] | None = empty(1)
