# error: expected list[float], got list[int]
# A caller's annotation cannot reinterpret a nonempty template result.
def numbers(n):
    return [n]


result: list[float] = numbers(1)
print(result)
