# An async def whose return type is inferred, returning a bool on one path and ending without a
# value on another, returns bool | None, as an ordinary function does (the next compile pass
# gives its coroutines that type from the start); also one that never suspends, whose await
# calls its twin, and whose coroutine made as a value returns int | None too
import types


@types.coroutine
def tick():
    yield


async def maybe(flag: bool):
    await tick()
    if flag:
        return True


async def direct(flag: bool):
    if flag:
        return 7


async def main() -> None:
    print(await maybe(True))
    print(await maybe(False))
    print(await direct(True), await direct(False))
    d = direct(False)
    try:
        d.send(None)
    except StopIteration:
        print("direct finished")


c = main()
try:
    while True:
        c.send(None)
except StopIteration:
    print("done")
