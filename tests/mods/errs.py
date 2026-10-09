# a module's exception classes: an uncaught one shows its module, "mods.errs.Missing: ..."


class StoreError(Exception):
    pass


class Missing(StoreError):
    def __init__(self, key: str):
        super().__init__(f"no key {key!r}")
        self.key = key


class Full(StoreError):
    def __init__(self, size: int):
        super().__init__("store full", size)
        self.size = size

    def __str__(self) -> str:
        return f"full at {self.size}"


class Store:
    def __init__(self, cap: int):
        self.cap = cap
        self.items: dict[str, int] = {}

    def get(self, k: str) -> int:
        if k not in self.items:
            raise Missing(k)
        return self.items[k]

    def put(self, k: str, v: int) -> None:
        if len(self.items) >= self.cap:
            raise Full(self.cap)
        self.items[k] = v


def checked(s: Store, k: str) -> int:
    try:
        return s.get(k)
    except Missing as e:
        print("checked:", e.key)
        return -1
