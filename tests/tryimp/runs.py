# How many times flaky's code has run (tests/programs/imports/import_try_binding.py)
n = 0


def incr() -> int:
    global n
    n += 1
    return n
