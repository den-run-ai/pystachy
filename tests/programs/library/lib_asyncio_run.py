# asyncio's event loop runs tasks as CPython's does: asyncio.run(), awaiting coroutines and
# tasks, create_task(), gather() of a list of coroutines (into a list of their results,
# list[None] for coroutines that return None), sleep(0) and timed sleeps, the eager task
# factory, call_soon() and call_later() callbacks in their order, Future callbacks,
# current_task(), get_running_loop() and run_until_complete() of a new loop. A Future names its
# result type (loop.create_future() is not supported: lib/compatibility.md#asyncio).
import asyncio

order: list[str] = []


async def child(n: int) -> int:
    order.append(f"start {n}")
    await asyncio.sleep(0)
    order.append(f"end {n}")
    return n * 10


async def quiet(n: int) -> None:
    await asyncio.sleep(0.001 * n)
    order.append(f"quiet {n}")


async def main() -> None:
    print("child", await child(1))
    t = asyncio.create_task(child(2))
    print("task", t.done(), await t, t.done(), t.result())
    order.clear()
    print("gather", await asyncio.gather(*[child(i) for i in range(4)]), order)
    order.clear()
    print("gather None", await asyncio.gather(*[quiet(i) for i in [3, 1, 2]]), order)
    loop = asyncio.get_running_loop()
    seen: list[str] = []
    loop.call_later(0.002, seen.append, "later")
    loop.call_soon(seen.append, "soon 1")
    loop.call_soon(seen.append, "soon 2")
    await asyncio.sleep(0.01)
    print("callbacks", seen)
    f: asyncio.Future[str] = asyncio.Future(loop=loop)
    f.add_done_callback(lambda fut: seen.append("done " + fut.result()))
    loop.call_soon(f.set_result, "x")
    print("future", await f)
    await asyncio.sleep(0)
    print("callbacks", seen)
    print("current", asyncio.current_task() is not None)


async def eager_main() -> None:
    loop = asyncio.get_running_loop()
    loop.set_task_factory(asyncio.eager_task_factory)
    order.clear()
    t = asyncio.create_task(child(5))
    order.append("created")
    print("eager", await t, order)


asyncio.run(main())
asyncio.run(eager_main())
loop = asyncio.new_event_loop()
print("run_until_complete", loop.run_until_complete(child(7)))
loop.close()
print("closed", loop.is_closed())
