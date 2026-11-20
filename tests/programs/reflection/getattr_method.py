# CPython calls __getattr__ where reading an attribute fails, here a field that __init__ may
# leave unassigned: the read tests the field's flag and calls the method (#1536).
class Config:
    def __init__(self, full: bool) -> None:
        if full:
            self.depth = 3
        self.name = "c"

    def __getattr__(self, name: str) -> int:
        return 0


print(Config(False).depth)
