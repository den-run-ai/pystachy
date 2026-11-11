# error: 'async' statements are not supported
class Lock:
    def __init__(self) -> None:
        self.held = False


async def guarded(lock: Lock) -> int:
    async with lock:
        return 1


guarded(Lock()).send(None)
