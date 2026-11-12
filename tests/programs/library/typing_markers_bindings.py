from typing import Callable, final


def local():
    def final(fn):
        print("local decorator")
        return fn

    @final
    def answer() -> int:
        return 9

    return answer


def default_effect() -> int:
    print("default")
    return 0


def optional(enabled: bool) -> Callable[[], int]:
    if enabled:
        from typing import final as marker

    @marker
    def answer(value: int = default_effect()) -> int:
        return 12

    return answer


print(local()())
try:
    optional(False)
except UnboundLocalError:
    print("missing marker before default")
print(optional(True)())


@final
def default(value: int = 14) -> int:
    return value


print(default())
