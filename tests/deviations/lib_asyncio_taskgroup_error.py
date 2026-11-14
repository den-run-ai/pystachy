# Documented deviation: exception groups are not supported, so a TaskGroup whose task fails raises
# that task's exception (the first, where several fail), once its other tasks are cancelled and
# done. CPython raises ExceptionGroup('unhandled errors in a TaskGroup', [ValueError('boom')]),
# which except* or an except clause of ExceptionGroup catches (lib/compatibility.md#asyncio).
import asyncio


async def fail() -> None:
    await asyncio.sleep(0)
    raise ValueError("boom")


async def slow() -> None:
    try:
        await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("slow cancelled")
        raise


async def main() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(fail())
            tg.create_task(slow())
    except Exception as e:
        print(type(e).__name__, e)


asyncio.run(main())
