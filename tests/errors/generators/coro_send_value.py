# error: cannot send int to Coroutine[None,None,int], whose send type is None: a coroutine is sent None (an awaitable's yield takes it)
async def value() -> int:
    return 1


c = value()
c.send(5)
