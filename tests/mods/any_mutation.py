from typing import Any


class Table:
    def __init__(self) -> None:
        self.items: dict[str, int] = {}

    def key(self, key: Any) -> str:
        if isinstance(key, int):
            return str(key)
        return key

    def __getitem__(self, key: Any) -> int:
        print("get", key)
        return self.items[self.key(key)]

    def __setitem__(self, key: Any, value: Any) -> Any:
        print("set", key, value)
        self.items[self.key(key)] = int(value)
        return value

    def __delitem__(self, key: object) -> Any:
        print("del", key)
        del self.items[self.key(key)]
        return key
