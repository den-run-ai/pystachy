# error: an object of a class that derives from dict is not stored or passed as a dict yet
class Made(dict[str, int]):
    pass


d: dict[str, int] = Made()
print(d)
