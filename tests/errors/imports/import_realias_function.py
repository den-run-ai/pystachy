# error: 'one' is bound by two imports, to different modules, functions or classes (not supported)
def first() -> int:
    from emods.realias import plus_one as one
    from emods.realias import minus_one as one
    return one(1)


print(first())
