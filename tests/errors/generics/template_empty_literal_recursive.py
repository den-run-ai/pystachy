# error: cannot infer what collect() returns: it calls itself before a use shows what the list it returns holds
def collect(n):
    if n == 0:
        return []
    result: list[str] = collect(n - 1)
    print(result)
    return [1.5]


print(collect(1))
