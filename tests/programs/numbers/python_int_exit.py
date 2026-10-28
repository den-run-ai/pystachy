# pystachy: python-int
# A SystemExit of an int | None of a module that opts in to promoting ints (docs/python-int.md), in a
# program without try (whose exit is no exception): its status is the promoting int's value
def code(v: int) -> int | None:
    return v if v > 0 else None


print("exiting")
raise SystemExit(code(2 ** 70 // 2 ** 67 - 5))
