def default(label: str, amount: int) -> int:
    print("default", label)
    return amount


class Hot:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, amount: int = default("hot", 2)) -> str:
        self.calls += 1
        if amount < 0:
            raise ValueError("hot")
        return "h" * amount


class Cold:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, amount: int = default("cold", 3)) -> str:
        self.calls += 1
        if amount < 0:
            raise ValueError("cold")
        return "c" * amount


evaluations = 0


def argument(value: int) -> int:
    global evaluations
    evaluations += 1
    print("argument", value)
    return value


def check(stream: Hot | Cold | None, explicit: bool, value: int) -> None:
    try:
        if explicit:
            print(stream.read(amount=argument(value)))
        else:
            print(stream.read())
    except ValueError as error:
        print("caught", error)
    except AttributeError:
        print("none")
    finally:
        print("finally")


hot = Hot()
cold = Cold()
items: list[Hot | Cold | None] = [hot, cold, None]
for item in items:
    check(item, False, 0)
    check(item, True, 1)
    check(item, True, -1)
print("counts", evaluations, hot.calls, cold.calls)
