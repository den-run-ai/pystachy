# error: a second exception base must define no methods or fields, which Extra does: the first base gives the object its own
class Extra(Exception):
    def note(self) -> str:
        return "extra"


class Both(ValueError, Extra):
    pass


raise Both("x")
