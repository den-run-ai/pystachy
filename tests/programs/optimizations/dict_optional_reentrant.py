events: list[str] = []


class Key:
    def __init__(self, value: int, action: int = 0) -> None:
        self.value = value
        self.action = action

    def __hash__(self) -> int:
        events.append("hash " + str(self.value))
        action = self.action
        self.action = 0
        if action == 1:
            table.clear()
        elif action == 2:
            table.clear()
            table[self] = 1701
        elif action == 3:
            raise ValueError("hash")
        return 7

    def __eq__(self, other: "Key") -> bool:
        events.append("eq " + str(self.value) + " " + str(other.value))
        action = eq_action[0]
        eq_action[0] = 0
        if action == 1:
            table.clear()
        elif action == 2:
            table[self] = 2901
        elif action == 3:
            raise ValueError("equality")
        return self.value == other.value


table: dict[Key, int] = {}
eq_action: list[int] = [0]


def read(query: Key) -> int:
    try:
        result = table.get(query)
        table.clear()
        if result is None:
            return -1
        return result + 10
    except ValueError as error:
        events.append(str(error))
        return -2


def test() -> None:
    for action in range(4):
        table.clear()
        table[Key(13)] = 1201
        events.clear()
        print("hash", action, read(Key(13, action)), events)
    for action in range(4):
        table.clear()
        table[Key(13)] = 1201
        events.clear()
        eq_action[0] = action
        print("eq", action, read(Key(13)), events)


test()
