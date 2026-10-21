class Factory:
    def empty(self, value):
        print("method", value)
        return []

    def __call__(self, value):
        print("call", value)
        return []


def receiver(present: bool) -> Factory:
    print("receiver", present)
    return Factory() if present else None


def argument(value: int) -> int:
    print("argument", value)
    return value


# Attribute lookup precedes arguments; calling a None callable checks after them.
for present in [True, False]:
    try:
        words: list[str] = receiver(present).empty(argument(1))
        words.append("method")
        print(words)
    except AttributeError as error:
        print(str(error))
    try:
        called: list[str] = receiver(present)(argument(2))
        called.append("call")
        print(called)
    except TypeError as error:
        print(str(error))
