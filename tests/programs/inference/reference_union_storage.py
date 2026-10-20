class Hot:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, amount: int = 1) -> str:
        self.calls += 1
        return "h" * amount


class Cold:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, amount: int = 1) -> str:
        self.calls += 1
        return "c" * amount


class Holder:
    def __init__(self, stream: Hot | Cold) -> None:
        self.stream: Hot | Cold = stream


def consume(stream: Hot | Cold, amount: int = 1) -> str:
    return stream.read(amount)


def check() -> None:
    hot = Hot()
    cold = Cold()
    items: list[Hot | Cold] = [hot, cold, hot]
    saved: dict[str, Hot | Cold] = {"hot": hot, "cold": cold}
    for item in items:
        holder = Holder(item)
        alias = holder.stream
        print(consume(alias, 2))
        if isinstance(alias, Hot):
            print(alias is hot, alias.calls)
        else:
            print(alias is cold, alias.calls)
    print(consume(saved["hot"]), consume(saved["cold"]))
    print(hot.calls, cold.calls)


check()
