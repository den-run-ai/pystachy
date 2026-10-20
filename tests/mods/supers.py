# exception classes of a module whose methods call their base's as super(C, self).m(...),
# super().m(...) and Base.m(self, ...), also in a static and a class method;
# tests/programs/exceptions/exc_super_imported.py imports it as a package's submodule (mods.supers) and as a module of
# its own (supers)


class StoreError(Exception):
    def __init__(self, what: str, code: int):
        super(StoreError, self).__init__(what, code)
        self.code = code

    def __str__(self) -> str:
        return "store: " + super(StoreError, self).__str__()

    def describe(self) -> str:
        return f"code {self.code}"

    @staticmethod
    def plain(e: "StoreError") -> str:
        # (super() and super(C, e) in a static method bind its first argument)
        return super(StoreError, e).__str__() + " " + super().__repr__()

    @classmethod
    def basic(cls, e: "StoreError") -> str:
        # (a class method's super() binds cls: super(C, e) and Base.m(e) take the object)
        return super(StoreError, e).__repr__() + " " + Exception.__str__(e)


class Missing(StoreError):
    def __init__(self, key: str):
        super().__init__(f"no key {key!r}", 2)
        self.key = key

    def __repr__(self) -> str:
        return "Missing/" + super(Missing, self).__repr__()

    def detail(self) -> str:
        return "missing, " + super(Missing, self).describe()

    def static(self) -> str:
        # (the base's static and class methods get no object)
        return super().plain(self) + " | " + super(Missing, self).basic(self)


class Full(StoreError):
    def __init__(self, size: int):
        StoreError.__init__(self, "full", size)

    def detail(self) -> str:
        return "full, " + StoreError.describe(self)


class Bad(ValueError):
    def __init__(self, data: dict[int, int]):
        s = "x%d" % len(data)
        super(Bad, self).__init__(s)
        self.data = data
