# Helper of tests/programs/imports/import_set_item_hash.py: a class the program does not use,
# whose body hashes an object of this module's class as the module is imported.
class H:
    def __init__(self) -> None:
        self.v = 1

    def __hash__(self) -> int:
        print("mods.set_hash: hash", self.v)
        return 1


h = H()


class Table:
    KEYS = {(h, 1)}
