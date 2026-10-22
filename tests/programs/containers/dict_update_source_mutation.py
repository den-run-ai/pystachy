# Typed dictionaries share the source-mutation guard with Any dict unions.
class Key:
    def __init__(self, value: int) -> None:
        self.value = value
        self.victims: list[dict["Key", int]] = []

    def __hash__(self) -> int:
        return self.value

    def __eq__(self, other: "Key") -> bool:
        for victim in self.victims:
            victim.clear()
        self.victims = []
        return self.value == other.value


for operation in range(3):
    key = Key(1)
    left = {key: 10}
    source = {Key(1): 20}
    key.victims = [source]
    try:
        if operation == 0:
            result = left | source
            print(len(result))
        elif operation == 1:
            left |= source
        else:
            left.update(source)
    except RuntimeError as error:
        print(operation, str(error))
    print(list(left.values()), len(source))
