# error: coro_override_types.py:9: error: overrides of A.work() return incompatible types; use a common return type
# Async overrides whose coroutines return an int and a str have no common result type, as
# ordinary overrides returning them have none (coro_override_join.py joins int and None).
class A:
    async def work(self):
        return 1

    async def run(self):
        return await self.work()


class B(A):
    async def work(self):
        return "s"


def drive(o: A) -> None:
    try:
        o.run().send(None)
    except StopIteration:
        print("done")


drive(A())
drive(B())
