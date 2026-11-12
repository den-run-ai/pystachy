# error: lib_asyncio_create_future.py:10: error: 'asyncio.events.AbstractEventLoop' object has no method 'create_future'
# A Future's result type is a type argument that its constructor's call must name, and
# create_future() takes no value that gives it: make one with asyncio.Future(loop=loop),
# annotated f: asyncio.Future[int] (lib/compatibility.md#asyncio).
import asyncio


async def main() -> None:
    loop = asyncio.get_running_loop()
    f = loop.create_future()
    loop.call_soon(f.set_result, 1)
    print(await f)


asyncio.run(main())
