# int | None of a module global whose function's value reads it (count = 1 if count is
# None else count + 1): the arm that does not read it types it.
count = None


def bump() -> None:
    global count
    count = 1 if count is None else count + 1


for _ in range(3):
    bump()
print(count)
