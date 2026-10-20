# sum() with a start of a list | None that is None


def nums(c: bool) -> list[int] | None:
    return [1, 2] if c else None


print(sum(nums(True), 5))
print(sum(nums(False), 5))
