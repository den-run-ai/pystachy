# error: cannot infer what collect() returns: it calls itself before a use shows what the list it returns holds
# Multiple recursive callers cannot give one populated result different layouts.
def empty(n):
    return []


def collect(n):
    if n == 0:
        return empty(n)
    words: list[str] = collect(n - 1)
    nums: list[int] = collect(n - 1)
    nums.append(n)
    print(words)
    return nums


print(collect(2))
