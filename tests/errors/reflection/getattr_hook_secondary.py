# error: getattr_hook_secondary.py:19: error: the special method __getattr__ of its base Base is not supported (CPython calls it for each attribute it does not find) in a hierarchy with a secondary base
# Pystachy calls the __getattr__ of a single-inheritance hierarchy (#1536): a class with a
# secondary base, here a trait (a method-only base with a base of its own), stays an error.
class Trait:
    def helper(self) -> int:
        return 1


class TraitPlus(Trait):
    def more(self) -> int:
        return 2


class Base:
    def __getattr__(self, name: str) -> int:
        return 2


class Both(Base, TraitPlus):
    pass


print(Both().helper(), Both().zz)
