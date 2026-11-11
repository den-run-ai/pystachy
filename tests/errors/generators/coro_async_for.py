# error: 'async' statements are not supported
class Ticks:
    def __init__(self, n: int) -> None:
        self.n = n


async def total(t: Ticks) -> int:
    s = 0
    async for i in t:
        s += i
    return s


total(Ticks(3)).send(None)
