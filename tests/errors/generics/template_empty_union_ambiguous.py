# error: returns an empty list taken as list[int]: give it a type first
# No arbitrary member is chosen when two container layouts fit the empty result.
def empty(n):
    return []


result: list[str] | list[float] = empty(1)
print(result)
