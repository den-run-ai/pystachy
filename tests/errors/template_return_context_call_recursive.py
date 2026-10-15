# error: cannot infer what collect() returns: it calls itself before a use shows what the list it returns holds
def collect(n):
    if n == 0:
        return []
    return [collect(n - 1)]


result: list[list[int]] = collect(2)
