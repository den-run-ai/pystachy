# error: newtype_import_closure.py:2: error: 'Meters' is read in meters() where Pystachy cannot tell that the import in it that binds 'Meters' has run
def meters(flag: bool) -> int:
    if flag:
        from mods.newtypes import Meters

    def get() -> int:
        return Meters(3)

    return get()


print(meters(True))
